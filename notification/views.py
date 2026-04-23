from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from .models import Notification
from academic.models import Classroom, Teacher
from students.models import Students
from accounts.models import User


@login_required
def send_notification(request):
    user = request.user
    
    if user.role not in ['SUPER_ADMIN', 'TEACHER']:
        messages.error(request, "You don't have permission to send notifications.")
        return redirect('dashboard')
    
    my_classes = []
    if user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            my_classes = Classroom.objects.filter(class_teacher=user).distinct()
        except Teacher.DoesNotExist:
            my_classes = []
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message_text = request.POST.get('message')
        notification_type = request.POST.get('notification_type')
        target_class_id = request.POST.get('target_class')
        
        if not title or not message_text:
            messages.error(request, "Please fill in both title and message.")
            return redirect('send_notification')
        
        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    sender=user,
                    title=title,
                    message=message_text,
                    notification_type=notification_type
                )
                
                if notification_type == 'CLASS' and target_class_id:
                    target_class = Classroom.objects.get(id=target_class_id)
                    notification.target_class = target_class
                    notification.save()
                    
                    students = Students.objects.filter(current_class=target_class)
                    for student in students:
                        Notification.objects.create(
                            sender=user,
                            recipient=student.user,
                            title=title,
                            message=message_text,
                            notification_type='STUDENT'
                        )
                
                elif notification_type == 'ALL' and user.role == 'SUPER_ADMIN':
                    all_users = User.objects.filter(is_active=True)
                    for u in all_users:
                        Notification.objects.create(
                            sender=user,
                            recipient=u,
                            title=title,
                            message=message_text,
                            notification_type='ALL'
                        )
                
                elif notification_type == 'TEACHER' and user.role == 'SUPER_ADMIN':
                    teachers = User.objects.filter(role='TEACHER')
                    for t in teachers:
                        Notification.objects.create(
                            sender=user,
                            recipient=t,
                            title=title,
                            message=message_text,
                            notification_type='TEACHER'
                        )
                
                elif notification_type == 'PARENT' and user.role == 'SUPER_ADMIN':
                    parents = User.objects.filter(role='PARENT')
                    for p in parents:
                        Notification.objects.create(
                            sender=user,
                            recipient=p,
                            title=title,
                            message=message_text,
                            notification_type='PARENT'
                        )
                
                messages.success(request, "Notification sent successfully!")
                return redirect('send_notification')
                
        except Exception as e:
            messages.error(request, f"Error sending notification: {e}")
    
    context = {'my_classes': my_classes, 'user_role': user.role}
    return render(request, 'notification/send.html', context)


@login_required
def user_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user).select_related('sender')
    
    if request.GET.get('mark_all_read'):
        notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('user_notifications')
    
    context = {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    }
    return render(request, 'notification/notification_list.html', context)


@login_required
def mark_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    return redirect('user_notifications')


@login_required
def mark_all_as_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('user_notifications')


@login_required
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    messages.success(request, "Notification deleted.")
    return redirect('user_notifications')


@login_required
def unread_count_api(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})