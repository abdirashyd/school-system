from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from .models import Students, Attendance
from django.utils import timezone
from academic.models import Classroom, Teacher, Subject
from datetime import datetime, timedelta
from django.utils import timezone
from .utils import export_attendance_to_excel


@login_required
def student_list_view(request):
    user = request.user
    search_query = request.GET.get('search', '')
    leadership_filter = request.GET.get('has_leadership', '')
    
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        students = Students.objects.all().select_related('current_class', 'parents')
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            class_teacher_classes = Classroom.objects.filter(class_teacher=user)
            subject_teacher_classes = Classroom.objects.filter(
                subjects__teacher=user
            ).values_list('id', flat=True).distinct()
            all_class_ids = list(class_teacher_classes.values_list('id', flat=True)) + list(subject_teacher_classes)
            if all_class_ids:
                students = Students.objects.filter(current_class_id__in=all_class_ids).select_related('current_class', 'parents')
            else:
                students = Students.objects.none()
        except Teacher.DoesNotExist:
            students = Students.objects.none()
    elif user.role == 'PARENT':
        students = Students.objects.filter(parents=user).select_related('current_class')
    elif user.role == 'STUDENT':
        messages.info(request, "You can only view your own profile.")
        if hasattr(user, 'student_record_records'):
            return redirect('students_detail', pk=user.student_record_records.id)
        else:
            students = Students.objects.none()
    else:
        students = Students.objects.none()
    
    if search_query:
        students = students.filter(
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(registration_number__icontains=search_query)
        )
    
    if leadership_filter == 'true':
        students = students.filter(has_leadership=True)
    elif leadership_filter == 'false':
        students = students.filter(has_leadership=False)
    
    return render(request, 'students/student_list.html', {
        'students': students,
        'search_query': search_query,
        'leadership_filter': leadership_filter,
    })


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Students, pk=pk)
    user = request.user
    
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        pass
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            is_class_teacher = (student.current_class and student.current_class.class_teacher == user)
            teaches_subject = Subject.objects.filter(
                teacher=user,
                classrooms=student.current_class
            ).exists()
            if not (is_class_teacher or teaches_subject):
                messages.error(request, "You don't have permission to view this student.")
                return redirect('student_list')
        except Teacher.DoesNotExist:
            messages.error(request, "Teacher record not found.")
            return redirect('student_list')
    elif user.role == 'PARENT':
        if student.parents != user:
            messages.error(request, "You can only view your own children.")
            return redirect('student_list')
    elif user.role == 'STUDENT':
        if not hasattr(user, 'student_record_records') or user.student_record_records != student:
            messages.error(request, "You can only view your own profile.")
            return redirect('student_list')
    
    return render(request, 'students/students_detail.html', {'student': student})


@login_required
def attendance_report(request):
    user = request.user
    
    if user.role not in ['SUPER_ADMIN', 'ADMIN', 'TEACHER']:
        messages.error(request, "You don't have permission to mark attendance.")
        return redirect('dashboard')
    
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        students = Students.objects.all().select_related('current_class')
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            class_teacher_classes = Classroom.objects.filter(class_teacher=user)
            subject_teacher_classes = Classroom.objects.filter(
                subjects__teacher=user
            ).values_list('id', flat=True).distinct()
            all_class_ids = list(class_teacher_classes.values_list('id', flat=True)) + list(subject_teacher_classes)
            if all_class_ids:
                students = Students.objects.filter(current_class_id__in=all_class_ids).select_related('current_class')
            else:
                students = Students.objects.none()
        except Teacher.DoesNotExist:
            students = Students.objects.none()
    else:
        students = Students.objects.none()
    
    today = timezone.now().date()
    
    if request.method == 'POST':
        saved_count = 0
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            remarks = request.POST.get(f'remarks_{student.id}', '')
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={'status': status, 'remarks': remarks, 'marked_by': user}
                )
                saved_count += 1
        if saved_count > 0:
            messages.success(request, f"Attendance for {saved_count} student(s) on {today} saved successfully!")
        else:
            messages.warning(request, "No attendance records were saved.")
        return redirect('attendance_report')
    
    attendance_records = {att.student_id: att for att in Attendance.objects.filter(date=today)}
    
    context = {
        'students': students,
        'attendance_records': attendance_records,
        'today': today,
        'status_choices': Attendance.STATUS_CHOICES,
    }
    return render(request, 'students/attendance_report.html', context)


@login_required
def delete_student(request, pk):
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can delete students.")
        return redirect('student_list')
    
    student = get_object_or_404(Students, pk=pk)
    name = f"{student.first_name} {student.last_name}"
    
    if student.user:
        student.user.delete()
    else:
        student.delete()
    
    messages.success(request, f"Student {name} deleted successfully!")
    return redirect('student_list')


# students/views.py - Add these imports at the top

  # Add this


@login_required
def attendance_report(request):
    user = request.user
    
    if user.role not in ['SUPER_ADMIN', 'ADMIN', 'TEACHER']:
        messages.error(request, "You don't have permission to mark attendance.")
        return redirect('dashboard')
    
    # Get students based on role
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        students = Students.objects.all().select_related('current_class')
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            class_teacher_classes = Classroom.objects.filter(class_teacher=user)
            subject_teacher_classes = Classroom.objects.filter(
                subjects__teacher=user
            ).values_list('id', flat=True).distinct()
            all_class_ids = list(class_teacher_classes.values_list('id', flat=True)) + list(subject_teacher_classes)
            if all_class_ids:
                students = Students.objects.filter(current_class_id__in=all_class_ids).select_related('current_class')
            else:
                students = Students.objects.none()
        except Teacher.DoesNotExist:
            students = Students.objects.none()
    else:
        students = Students.objects.none()
    
    # Get date range from request
    today = timezone.now().date()
    default_start = today - timedelta(days=30)
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = default_start
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = today
    
    # Get attendance records within date range
    attendance_records = {}
    for student in students:
        records = Attendance.objects.filter(
            student=student,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        attendance_records[student.id] = records
    
    # Check if download requested
    if request.GET.get('export') == 'excel':
        classroom_name = request.GET.get('class_name', 'All Classes')
        return export_attendance_to_excel(
            students, 
            attendance_records, 
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d'),
            classroom_name
        )
    
    # For POST request (mark attendance)
    if request.method == 'POST':
        saved_count = 0
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            remarks = request.POST.get(f'remarks_{student.id}', '')
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={'status': status, 'remarks': remarks, 'marked_by': user}
                )
                saved_count += 1
        if saved_count > 0:
            messages.success(request, f"Attendance for {saved_count} student(s) on {today} saved successfully!")
        else:
            messages.warning(request, "No attendance records were saved.")
        return redirect('attendance_report')
    
    # Get today's attendance records
    today_records = {att.student_id: att for att in Attendance.objects.filter(date=today)}
    
    context = {
        'students': students,
        'today_records': today_records,
        'today': today,
        'status_choices': Attendance.STATUS_CHOICES,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'students/attendance_report.html', context)