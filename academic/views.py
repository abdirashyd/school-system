from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from .models import Teacher, Classroom, Subject, Exam, Results
from django.shortcuts import get_object_or_404


@login_required
def teacher_list(request):
    user = request.user
    search_query = request.GET.get('search', '')
    
    # SUPER ADMIN / ADMIN - See all teachers
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        teachers = Teacher.objects.all().select_related('user')
    # TEACHER - See only themselves
    elif user.role == 'TEACHER':
        teachers = Teacher.objects.filter(user=user).select_related('user')
    else:
        teachers = Teacher.objects.none()
    
    # Apply search filter
    if search_query:
        teachers = teachers.filter(
            models.Q(name__icontains=search_query) |
            models.Q(tsc_number__icontains=search_query) |
            models.Q(user__email__icontains=search_query) |
            models.Q(user__first_name__icontains=search_query) |
            models.Q(user__last_name__icontains=search_query)
        )
    
    return render(request, 'academic/teacher_list.html', {
        'teachers': teachers,
        'search_query': search_query,
    })


@login_required
def results(request):
    user = request.user
    
    # SUPER ADMIN / ADMIN - See all results
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        results = Results.objects.all().select_related('student', 'subject', 'exam')
    
    # TEACHER - See only results for subjects they teach
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            # Get subjects taught by this teacher (through Subject.teacher field)
            taught_subject_ids = Subject.objects.filter(
                teacher=user
            ).values_list('id', flat=True).distinct()
            results = Results.objects.filter(
                subject_id__in=taught_subject_ids
            ).select_related('student', 'subject', 'exam')
        except Teacher.DoesNotExist:
            results = Results.objects.none()
    
    # STUDENT - See only their own results
    elif user.role == 'STUDENT':
        if hasattr(user, 'student_record_records'):
            results = Results.objects.filter(
                student=user.student_record_records
            ).select_related('subject', 'exam')
        else:
            results = Results.objects.none()
    
    # PARENT - See results for their children
    elif user.role == 'PARENT':
        from students.models import Students
        children = Students.objects.filter(parents=user)
        results = Results.objects.filter(
            student__in=children
        ).select_related('student', 'subject', 'exam')
    
    else:
        results = Results.objects.none()
    
    return render(request, 'academic/results.html', {'results': results})


@login_required
def exam_list(request):
    exams = Exam.objects.all()
    return render(request, 'academic/exam_list.html', {'exams': exams})


@login_required
def classroom_list(request):
    user = request.user
    
    # SUPER ADMIN / ADMIN - See all classrooms
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        classrooms = Classroom.objects.all().select_related('class_teacher')
    
    # TEACHER - See only their classes
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            # Classes where teacher is CLASS TEACHER
            class_teacher_classes = Classroom.objects.filter(class_teacher=user)
            # Classes where teacher teaches a SUBJECT (through Subject.teacher field)
            subject_teacher_classes = Classroom.objects.filter(
                subjects__teacher=user
            ).distinct()
            classrooms = (class_teacher_classes | subject_teacher_classes).distinct().select_related('class_teacher')
        except Teacher.DoesNotExist:
            classrooms = Classroom.objects.none()
    
    # STUDENT - See only their own class
    elif user.role == 'STUDENT':
        if hasattr(user, 'student_record_records') and user.student_record_records.current_class:
            classrooms = Classroom.objects.filter(id=user.student_record_records.current_class.id)
        else:
            classrooms = Classroom.objects.none()
    
    # PARENT - See classes of their children
    elif user.role == 'PARENT':
        from students.models import Students
        children = Students.objects.filter(parents=user)
        classroom_ids = children.exclude(current_class=None).values_list('current_class_id', flat=True).distinct()
        classrooms = Classroom.objects.filter(id__in=classroom_ids)
    
    else:
        classrooms = Classroom.objects.none()
    
    return render(request, 'academic/classroom_list.html', {'classrooms': classrooms})


@login_required
def subject_list(request):
    user = request.user
    
    # SUPER ADMIN / ADMIN - See all subjects
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        subjects = Subject.objects.all().select_related('teacher')
    
    # TEACHER - See only subjects they teach
    elif user.role == 'TEACHER':
        subjects = Subject.objects.filter(teacher=user).select_related('teacher')
    
    # STUDENT - See subjects in their class
    elif user.role == 'STUDENT':
        if hasattr(user, 'student_record_records') and user.student_record_records.current_class:
            subjects = user.student_record_records.current_class.subjects.all()
        else:
            subjects = Subject.objects.none()
    
    # PARENT - See subjects from their children's classes
    elif user.role == 'PARENT':
        from students.models import Students
        children = Students.objects.filter(parents=user)
        subjects = Subject.objects.none()
        for child in children:
            if child.current_class:
                subjects = subjects | child.current_class.subjects.all()
        subjects = subjects.distinct()
    
    else:
        subjects = Subject.objects.none()
    
    return render(request, 'academic/subject_list.html', {'subjects': subjects})


@login_required
def add_classroom(request):
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can add classrooms.")
        return redirect('classroom_list')
    
    from accounts.models import User
    teachers = User.objects.filter(role='TEACHER')

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        stream = request.POST.get('stream', '').strip()
        fee_amount = request.POST.get('fee_amount', 0)
        class_teacher_id = request.POST.get('class_teacher')

        if not name or not stream:
            messages.error(request, "Class Name and Stream are required!")
        else:
            try:
                Classroom.objects.create(
                    name=name,
                    stream=stream,
                    fee_amount=fee_amount or 0,
                    class_teacher_id=class_teacher_id if class_teacher_id else None
                )
                messages.success(request, f"Classroom '{name} {stream}' added successfully!")
                return redirect('classroom_list')
            except Exception as e:
                messages.error(request, f"Error creating classroom: {e}")

    return render(request, 'academic/add_classroom.html', {'teachers': teachers})


@login_required
def add_subject(request):
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can add subjects.")
        return redirect('subject_list')
    
    teachers = Teacher.objects.all()

    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '')
        teacher_id = request.POST.get('teacher')

        if not name or not code:
            messages.error(request, "Subject Name and Code are required!")
        else:
            try:
                subject = Subject.objects.create(name=name, code=code, description=description)
                if teacher_id:
                    subject.teacher_id = teacher_id
                    subject.save()
                messages.success(request, f"Subject '{name} ({code})' added successfully!")
                return redirect('subject_list')
            except Exception as e:
                messages.error(request, f"Error adding subject: {e}")

    return render(request, 'academic/add_subject.html', {'teachers': teachers})


@login_required
def add_exam(request):
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can add exams.")
        return redirect('exam_list')
    
    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        exam_type = request.POST.get('exam_type')
        date_started = request.POST.get('date_started')

        if not name or not exam_type or not date_started:
            messages.error(request, "All fields are required!")
        else:
            try:
                Exam.objects.create(name=name, exam_type=exam_type, date_started=date_started)
                messages.success(request, f"Exam '{name}' added successfully!")
                return redirect('exam_list')
            except Exception as e:
                messages.error(request, f"Error saving exam: {e}")

    return render(request, 'academic/add_exam.html', {'exam_type': Exam.EXAM_TYPE})


@login_required
def add_results(request):
    from students.models import Students
    
    user = request.user
    
    if user.role not in ['SUPER_ADMIN', 'ADMIN', 'TEACHER']:
        messages.error(request, "You don't have permission to add results.")
        return redirect('results')
    
    # Get students based on role
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        students = Students.objects.all().select_related('current_class')
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            class_teacher_classes = Classroom.objects.filter(class_teacher=user).values_list('id', flat=True)
            subject_teacher_classes = Classroom.objects.filter(
                subjects__teacher=user
            ).values_list('id', flat=True).distinct()
            all_classes = set(list(subject_teacher_classes) + list(class_teacher_classes))
            if all_classes:
                students = Students.objects.filter(current_class_id__in=all_classes).select_related('current_class')
            else:
                students = Students.objects.none()
        except Teacher.DoesNotExist:
            students = Students.objects.none()
    else:
        students = Students.objects.none()
    
    # Get subjects based on role
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        subjects = Subject.objects.all()
    elif user.role == 'TEACHER':
        subjects = Subject.objects.filter(teacher=user)
    else:
        subjects = Subject.objects.none()
    
    exams = Exam.objects.all()

    if request.method == "POST":
        student_id = request.POST.get('student')
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        marks = request.POST.get('marks_obtained')
        remarks = request.POST.get('teacher_remark', '')

        if not all([student_id, exam_id, subject_id, marks]):
            messages.error(request, "Please fill all required fields!")
            return redirect('add_results')

        # Verify teacher has permission
        if user.role == 'TEACHER':
            try:
                student = Students.objects.get(id=student_id)
                subject = Subject.objects.get(id=subject_id)
                if subject.teacher != user:
                    messages.error(request, "You don't have permission to add results for this subject.")
                    return redirect('add_results')
                if student.current_class and not student.current_class.subjects.filter(id=subject_id).exists():
                    messages.error(request, "This subject is not taught in the student's class.")
                    return redirect('add_results')
            except Exception as e:
                messages.error(request, f"Permission error: {e}")
                return redirect('add_results')

        try:
            marks = int(marks)
            if marks < 0 or marks > 100:
                messages.error(request, "Marks must be between 0 and 100.")
                return redirect('add_results')
        except ValueError:
            messages.error(request, "Invalid marks value!")
            return redirect('add_results')

        try:
            Results.objects.update_or_create(
                student_id=student_id,
                subject_id=subject_id,
                exam_id=exam_id,
                defaults={
                    'marks_obtained': marks,
                    'teacher_remark': remarks,
                    'out_of': 100
                }
            )
            messages.success(request, "Results saved successfully!")
            return redirect('results')
        except Exception as e:
            messages.error(request, f"Save Error: {e}")

    return render(request, 'academic/add_results.html', {
        'students': students,
        'exams': exams,
        'subjects': subjects
    })


@login_required
def delete_teacher(request, pk):
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can delete teachers.")
        return redirect('teacher_list')
    
    teacher = get_object_or_404(Teacher, pk=pk)
    name = teacher.name
    
    if teacher.user:
        teacher.user.delete()
    else:
        teacher.delete()
    
    messages.success(request, f"Teacher {name} deleted successfully!")
    return redirect('teacher_list')


# academic/views.py - Add these functions

from django.db import IntegrityError
from .models import Schedule


@login_required
def schedule_list(request):
    """View all schedules - Admin only"""
    if request.user.role not in ['SUPER_ADMIN', 'ADMIN']:
        messages.error(request, "You don't have permission to view schedules.")
        return redirect('dashboard')
    
    # Get all schedules organized by day
    schedules = Schedule.objects.all().select_related('subject', 'teacher', 'classroom')
    
    # Organize by day
    schedule_by_day = {
        'MONDAY': [],
        'TUESDAY': [],
        'WEDNESDAY': [],
        'THURSDAY': [],
        'FRIDAY': [],
        'SATURDAY': []
    }
    
    for schedule in schedules:
        schedule_by_day[schedule.day].append(schedule)
    
    context = {
        'schedule_by_day': schedule_by_day,
    }
    return render(request, 'academic/schedule_list.html', context)


@login_required
def add_schedule(request):
    """Add a new schedule - Admin only"""
    if request.user.role not in ['SUPER_ADMIN', 'ADMIN']:
        messages.error(request, "You don't have permission to add schedules.")
        return redirect('dashboard')
    
    subjects = Subject.objects.all()
    teachers = Teacher.objects.all()
    classrooms = Classroom.objects.all()
    
    if request.method == 'POST':
        try:
            day = request.POST.get('day')
            subject_id = request.POST.get('subject')
            teacher_id = request.POST.get('teacher')
            classroom_id = request.POST.get('classroom')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            room = request.POST.get('room', '')
            
            # Validate
            if not all([day, subject_id, teacher_id, classroom_id, start_time, end_time]):
                messages.error(request, "Please fill all required fields.")
                return redirect('add_schedule')
            
            # Check if start_time < end_time
            if start_time >= end_time:
                messages.error(request, "End time must be after start time.")
                return redirect('add_schedule')
            
            subject = Subject.objects.get(id=subject_id)
            teacher = Teacher.objects.get(id=teacher_id)
            classroom = Classroom.objects.get(id=classroom_id)
            
            Schedule.objects.create(
                day=day,
                subject=subject,
                teacher=teacher,
                classroom=classroom,
                start_time=start_time,
                end_time=end_time,
                room=room
            )
            messages.success(request, "Schedule added successfully!")
            return redirect('schedule_list')
            
        except Subject.DoesNotExist:
            messages.error(request, "Subject not found.")
        except Teacher.DoesNotExist:
            messages.error(request, "Teacher not found.")
        except Classroom.DoesNotExist:
            messages.error(request, "Classroom not found.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    context = {
        'subjects': subjects,
        'teachers': teachers,
        'classrooms': classrooms,
    }
    return render(request, 'academic/add_schedule.html', context)


@login_required
def edit_schedule(request, schedule_id):
    """Edit a schedule - Admin only"""
    if request.user.role not in ['SUPER_ADMIN', 'ADMIN']:
        messages.error(request, "You don't have permission to edit schedules.")
        return redirect('dashboard')
    
    schedule = get_object_or_404(Schedule, id=schedule_id)
    subjects = Subject.objects.all()
    teachers = Teacher.objects.all()
    classrooms = Classroom.objects.all()
    
    if request.method == 'POST':
        try:
            day = request.POST.get('day')
            subject_id = request.POST.get('subject')
            teacher_id = request.POST.get('teacher')
            classroom_id = request.POST.get('classroom')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            room = request.POST.get('room', '')
            
            if not all([day, subject_id, teacher_id, classroom_id, start_time, end_time]):
                messages.error(request, "Please fill all required fields.")
                return redirect('edit_schedule', schedule_id=schedule_id)
            
            if start_time >= end_time:
                messages.error(request, "End time must be after start time.")
                return redirect('edit_schedule', schedule_id=schedule_id)
            
            subject = Subject.objects.get(id=subject_id)
            teacher = Teacher.objects.get(id=teacher_id)
            classroom = Classroom.objects.get(id=classroom_id)
            
            schedule.day = day
            schedule.subject = subject
            schedule.teacher = teacher
            schedule.classroom = classroom
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.room = room
            schedule.save()
            
            messages.success(request, "Schedule updated successfully!")
            return redirect('schedule_list')
            
        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    context = {
        'schedule': schedule,
        'subjects': subjects,
        'teachers': teachers,
        'classrooms': classrooms,
    }
    return render(request, 'academic/edit_schedule.html', context)


@login_required
def delete_schedule(request, schedule_id):
    """Delete a schedule - Admin only"""
    if request.user.role not in ['SUPER_ADMIN', 'ADMIN']:
        messages.error(request, "You don't have permission to delete schedules.")
        return redirect('dashboard')
    
    schedule = get_object_or_404(Schedule, id=schedule_id)
    schedule.delete()
    messages.success(request, "Schedule deleted successfully!")
    return redirect('schedule_list')