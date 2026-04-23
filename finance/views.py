from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Payement
from students.models import Students
from .mpesa_utility import stk_push
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import datetime


@login_required
def payement_detail(request):
    """View all payment records"""
    user = request.user
    
    if user.role == 'TEACHER':
        messages.info(request, "Finance section is not available for teachers.")
        return redirect('dashboard')
    
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        payments = Payement.objects.all().select_related('student')
    elif user.role == 'STUDENT':
        if hasattr(user, 'student_record_records'):
            payments = Payement.objects.filter(student=user.student_record_records).select_related('student')
        else:
            payments = Payement.objects.none()
    elif user.role == 'PARENT':
        children = Students.objects.filter(parents=user)
        payments = Payement.objects.filter(student__in=children).select_related('student')
    else:
        payments = Payement.objects.none()
    
    return render(request, 'finance/payement_detail.html', {'payments': payments})


@login_required
def process_payment(request):
    """Record a payment manually (Admin only)"""
    if request.user.role not in ['SUPER_ADMIN', 'ADMIN']:
        messages.error(request, "Only administrators can process payments.")
        return redirect('payement_detail')
    
    if request.method == 'POST':
        amount = request.POST.get('amount_paid')
        ref_code = request.POST.get('reference', '').upper()
        reg_number = request.POST.get('reg_number')
        month = request.POST.get('month')
        year = request.POST.get('year', 2026)
        
        if not all([amount, ref_code, reg_number, month]):
            messages.error(request, "Please fill all required fields.")
            return redirect('payement_detail')
        
        try:
            amount = float(amount)
        except ValueError:
            messages.error(request, "Invalid amount.")
            return redirect('payement_detail')
        
        student = Students.objects.filter(registration_number=reg_number).first()
        
        if not student:
            messages.error(request, f"Student '{reg_number}' not found!")
            return redirect('payement_detail')
        
        Payement.objects.create(
            student=student,
            amount_paid=amount,
            reference=ref_code,
            method=request.POST.get('method', 'M-Pesa'),
            month=int(month),
            year=int(year),
            recorded_by=request.user
        )
        
        # Send notifications
        from notification.models import Notification
        from accounts.models import User
        
        Notification.objects.create(
            sender=request.user,
            recipient=student.user,
            title="💰 Payment Received",
            message=f"KES {amount:,.2f} payment recorded. Reference: {ref_code}",
            notification_type='FEE'
        )
        
        if student.parents:
            Notification.objects.create(
                sender=request.user,
                recipient=student.parents,
                title=f"💰 Payment Received - {student.first_name}",
                message=f"KES {amount:,.2f} payment recorded. Reference: {ref_code}",
                notification_type='FEE'
            )
        
        messages.success(request, f"Payment of KES {amount:,.2f} recorded for {student.first_name} {student.last_name}!")
        return redirect('payement_detail')
    
    return redirect('payement_detail')


@login_required
def mpesa_payment(request):
    """Handle M-Pesa STK Push - Automatic payment"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        amount = request.POST.get('amount')
        reg_number = request.POST.get('reg_number')
        month = request.POST.get('month')
        
        if not all([phone_number, amount, reg_number, month]):
            messages.error(request, "Please fill all fields.")
            return redirect('payement_detail')
        
        student = Students.objects.filter(registration_number=reg_number).first()
        if not student:
            messages.error(request, f"Student '{reg_number}' not found!")
            return redirect('payement_detail')
        
        # Create pending payment record
        payment = Payement.objects.create(
            student=student,
            amount_paid=amount,
            reference=f"PENDING_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            method='M-Pesa',
            month=int(month),
            year=2026,
            recorded_by=request.user if request.user.is_authenticated else None
        )
        
        # Initiate STK Push
        result = stk_push(
            phone_number=phone_number,
            amount=amount,
            reg_number=reg_number,
            transaction_desc=f"Fee payment for {student.first_name} {student.last_name}"
        )
        
        if result.get('ResponseCode') == '0':
            payment.reference = result.get('CheckoutRequestID')
            payment.save()
            messages.success(request, "M-Pesa prompt sent! Check your phone and enter your PIN.")
        else:
            payment.delete()
            error_msg = result.get('errorMessage', result.get('error', 'Payment failed'))
            messages.error(request, f"Payment failed: {error_msg}")
        
        return redirect('payement_detail')
    
    return redirect('payement_detail')


@csrf_exempt
def mpesa_callback(request):
    """M-Pesa callback URL - Updates payment when confirmed"""
    try:
        data = json.loads(request.body)
        print("=" * 50)
        print("M-PESA CALLBACK RECEIVED")
        print(data)
        print("=" * 50)
        
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        
        if result_code == 0:
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            mpesa_receipt = None
            amount = None
            
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'Amount':
                    amount = item.get('Value')
            
            payment = Payement.objects.filter(reference=checkout_request_id).first()
            if payment:
                payment.reference = mpesa_receipt
                payment.save()
                
                from notification.models import Notification
                Notification.objects.create(
                    recipient=payment.student.user,
                    sender=None,
                    title="✅ Payment Successful",
                    message=f"KES {amount} payment confirmed. Reference: {mpesa_receipt}",
                    notification_type='FEE'
                )
                
                if payment.student.parents:
                    Notification.objects.create(
                        recipient=payment.student.parents,
                        sender=None,
                        title=f"✅ Payment Successful - {payment.student.first_name}",
                        message=f"KES {amount} payment confirmed. Reference: {mpesa_receipt}",
                        notification_type='FEE'
                    )
            
            print(f"✅ Payment Successful! Receipt: {mpesa_receipt}, Amount: {amount}")
        else:
            result_desc = stk_callback.get('ResultDesc', 'Payment failed')
            payment = Payement.objects.filter(reference=checkout_request_id).first()
            if payment:
                payment.delete()
            print(f"❌ Payment Failed: {result_desc}")
        
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
        
    except Exception as e:
        print(f"Callback error: {e}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)})