from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from .models import User
from academic.models import Classroom, Teacher, Subject
from students.models import Students
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import models
from django.conf import settings

def generate_parent_id():
    """
    Generate a unique Parent ID like: PRT-2024-001
    """
    import random
    import datetime
    
    year = datetime.datetime.now().year
    # Get count of existing parents
    parent_count = User.objects.filter(role='PARENT').count()
    next_number = parent_count + 1
    
    # Format: PRT-2024-001
    return f"PRT-{year}-{next_number:03d}"


@login_required
def dashboard_view(request):
    user = request.user
    
    # ========== SUPER ADMIN / ADMIN DASHBOARD ==========
    if user.role in ['SUPER_ADMIN', 'ADMIN']:
        from django.db.models import Count, Q
        from academic.models import Results
        from django.db.models import Avg

        subjects = Subject.objects.all()
        improvements = []
        
        for subject in subjects:
            avg_marks = Results.objects.filter(subject=subject).aggregate(Avg('marks_obtained'))['marks_obtained__avg']

            if avg_marks:
                percentage = round(avg_marks)
                improvements.append({
                    'name': subject.name,
                    'percentage': percentage,
                    'color': 'fill-blue'
                })
            else:
                improvements.append({
                    'name': subject.name,
                    'percentage': 0,
                    'color': 'fill-blue'
                })
            improvements = improvements[:5]
        
        student_count = Students.objects.count()
        teacher_count = Teacher.objects.count()
        class_count = Classroom.objects.count()
        recent_students = Students.objects.all().order_by('-id')[:5]
        top_subjects = Subject.objects.all()[:5]
        
        # GET CLASSROOM GENDER DATA FOR CHART
        classrooms = Classroom.objects.all()
        chart_data = []
        
        for classroom in classrooms:
            boys = Students.objects.filter(current_class=classroom, gender='MALE').count()
            girls = Students.objects.filter(current_class=classroom, gender='FEMALE').count()
            chart_data.append({
                'class_name': f"{classroom.name} {classroom.stream}" if classroom.stream else classroom.name,
                'boys': boys,
                'girls': girls,
            })
        
        context = {
            'total_students': student_count,
            'total_teachers': teacher_count,
            'total_classes': class_count,
            'recent_students': recent_students,
            'fee_collection': "300,000",
            'top_subjects': top_subjects,
            'chart_data': chart_data,
            'school_plan': 'Basic',
            'plan_expiry': '01/05/2024',
            'improvements': improvements,
        }
        return render(request, 'dashboard.html', context)
    
    # ========== TEACHER DASHBOARD ==========
    elif user.role == 'TEACHER':
        try:
            teacher_record = Teacher.objects.get(user=user)
            # Classes where teacher is CLASS TEACHER
            my_classes = Classroom.objects.filter(class_teacher=user).distinct()
            
            total_students = Students.objects.filter(
                current_class__in=my_classes
            ).count()
            
            # Subjects taught by this teacher
            my_subjects_count = Subject.objects.filter(teacher=user).count()
            
            context = {
                'my_classes': my_classes,
                'total_students': total_students,
                'my_subjects': my_subjects_count,
                'pending_results': 0,
            }
            return render(request, 'dashboard.html', context)
        except Teacher.DoesNotExist:
            return render(request, 'dashboard.html', {'my_classes': [], 'my_subjects': 0, 'total_students': 0, 'pending_results': 0})
        # ========== STUDENT - Redirect to profile ==========
    if user.role == 'STUDENT':
        if hasattr(user, 'student_record_records'):
            return redirect('students_detail', pk=user.student_record_records.id)
        else:
            messages.error(request, "Student profile not found.")
            return redirect('dashboard')
    
    # ========== PARENT - Redirect to children or profile ==========
    elif user.role == 'PARENT':
        from students.models import Students
        children = Students.objects.filter(parents=user)
        if children.count() == 1:
            return redirect('students_detail', pk=children.first().id)
        elif children.count() > 1:
            # Show list of children using student_list template
            return render(request, 'students/student_list.html', {
                'students': children,
                'is_parent_view': True
            })
        else:
            messages.error(request, "No children linked to your account.")
            return redirect('dashboard')
    return render(request, 'dashboard.html', {'error': 'Role not recognized'})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_approved:
                messages.error(request, "Your account is pending approval. Please contact the administrator.")
                return render(request, 'accounts/login.html')
            login(request, user)
          
            if user.role == 'STUDENT':
                if hasattr(user, 'student_record_records'):
                    return redirect('students_detail', pk=user.student_record_records.id)
                else:
                    messages.error(request, "Student profile not found.")
                    return redirect('dashboard')
            elif user.role == 'TEACHER':
                return redirect('dashboard')
            elif user.role == 'PARENT':
                from students.models import Students
                children = Students.objects.filter(parents=user)
                if children.exists():
                    return redirect('students_detail', pk=children.first().id)
                else:
                    messages.error(request, "No children linked to your account.")
                    return redirect('dashboard')
            else:
                return redirect('dashboard')

    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


@user_passes_test(lambda u: u.is_staff or u.role in ['ADMIN', 'SUPER_ADMIN'])
def admin_reset_password(request, user_id):
    if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
        messages.error(request, "You don't have permission to reset passwords.")
        return redirect('dashboard')
    
    user_to_reset = get_object_or_404(User, id=user_id)
    default_pass = settings.DEFAULT_PASSWORD
    user_to_reset.set_password(default_pass)
    user_to_reset.save()
    
    messages.success(request, f"Password for {user_to_reset.username} reset to: {default_pass}")
    return redirect('user_list')


def register_student_view(request):
    if request.user.is_authenticated and request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can register students.")
        return redirect('dashboard')
    
    if request.method == "POST":
        class_id = request.POST.get('grade_level')
        parent_id = request.POST.get('parent_id')
        gender = request.POST.get('gender')
        has_leadership = request.POST.get('has_leadership') == 'true'
        address = request.POST.get('address')
        medical_condition = request.POST.get('medical_condition')
        
        if not class_id:
            messages.error(request, "Please select a grade/classroom.")
            return redirect('register_students')

        try:
            with transaction.atomic():
                selected_class = Classroom.objects.get(id=class_id)
                admission_number = request.POST.get('admission_number')
                admission_number = admission_number.strip().upper()
                
                if Students.objects.filter(registration_number=admission_number).exists():
                    messages.error(request, f"Student with admission number {admission_number} already exists!")
                    return redirect('register_students')
                
                if User.objects.filter(username=admission_number).exists():
                    messages.error(request, f"Username {admission_number} is already taken!")
                    return redirect('register_students')
                
                user = User.objects.create_user(
                    username=admission_number,
                    email=request.POST.get('email'),
                    password=settings.DEFAULT_PASSWORD,
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    role='STUDENT',
                    is_approved=True
                )

                student = Students.objects.create(
                    user=user,
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    registration_number=admission_number,
                    current_class=selected_class,
                    parents_id=parent_id if parent_id else None,
                    gender=gender,
                    has_leadership=has_leadership,
                    address=address,
                    medical_condition=medical_condition,
                )

                # ✅ ADD THIS: Notify Class Teacher
                if selected_class.class_teacher:
                    from notification.models import Notification
                    Notification.objects.create(
                        sender=request.user,
                        recipient=selected_class.class_teacher,
                        title="👨‍🎓 New Student Added",
                        message=f"{student.first_name} {student.last_name} ({admission_number}) has been added to {selected_class.name} {selected_class.stream or ''}.",
                        notification_type='STUDENT'
                    )
                    messages.info(request, f"Notification sent to {selected_class.class_teacher.get_full_name()}")

                messages.success(request, f"Student {admission_number} registered successfully!")
                messages.info(request, f"Username: {admission_number} | Password: {settings.DEFAULT_PASSWORD}")
                return redirect('user_list')

        except Classroom.DoesNotExist:
            messages.error(request, "Selected classroom does not exist!")
        except Exception as e:
            messages.error(request, f"Error: {e}")

    all_classrooms = Classroom.objects.all()
    all_parents = User.objects.filter(role='PARENT')
    return render(request, 'accounts/register_form.html', {
        'classrooms': all_classrooms,
        'parents': all_parents,
    })

def register_teacher_view(request):
    # Only Super Admin can register teachers
    if request.user.is_authenticated and request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can register teachers.")
        return redirect('dashboard')
    
    if request.method == "POST":
        email = request.POST.get('email')
        tsc_number = request.POST.get('tsc_number')
        f_name = request.POST.get('first_name')
        l_name = request.POST.get('last_name')
        subject_id = request.POST.get('assigned_subject')  # OPTIONAL
        
        # New fields
        date_of_joining = request.POST.get('date_of_joining')
        experience = request.POST.get('experience')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        qualification = request.POST.get('qualification')
        
        # Clean the TSC number
        tsc_number = tsc_number.strip().upper()
        
        # Check if teacher already exists
        if Teacher.objects.filter(tsc_number=tsc_number).exists():
            messages.error(request, f"Teacher with TSC number {tsc_number} already exists!")
            return redirect('register_teacher')
        
        if User.objects.filter(username=tsc_number).exists():
            messages.error(request, f"Username {tsc_number} is already taken!")
            return redirect('register_teacher')
        
        try:
            with transaction.atomic():
                # Create User
                user = User.objects.create_user(
                    username=tsc_number,
                    email=email,
                    password=settings.DEFAULT_PASSWORD,
                    first_name=f_name,
                    last_name=l_name,
                    role='TEACHER',
                    is_approved=True,
                    phone_number=phone,
                )

                # Create Teacher
                teacher = Teacher.objects.create(
                    user=user,
                    name=f"{f_name} {l_name}",
                    tsc_number=tsc_number,
                    phone=phone,
                    address=address,
                    date_of_joining=date_of_joining if date_of_joining else None,
                    experience=experience if experience else None,
                    qualification=qualification if qualification else None,
                )

                # Assign subject ONLY if selected (OPTIONAL)
                if subject_id:
                    try:
                        subject_obj = Subject.objects.get(id=subject_id)
                        subject_obj.teacher = user
                        subject_obj.save()
                        messages.info(request, f"Subject {subject_obj.name} assigned to teacher.")
                    except Subject.DoesNotExist:
                        messages.warning(request, "Selected subject not found. You can assign subject later.")

                messages.info(request, f"Username: {tsc_number} | Password: {settings.DEFAULT_PASSWORD}")
                messages.info(request, f"Username: {tsc_number} | Password: Teacher@2026")
                return redirect('teacher_list')
                
        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    subjects = Subject.objects.all()
    return render(request, 'accounts/register_form.html', {'subjects': subjects})


@login_required
def user_list_view(request):
    if request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
        messages.error(request, "You don't have permission to view user list.")
        return redirect('dashboard')
    
    role_filter = request.GET.get('role')
    search_query = request.GET.get('search', '')
    
    if role_filter:
        all_users = User.objects.filter(role=role_filter).order_by('-date_joined')
    else:
        all_users = User.objects.all().order_by('-date_joined')
    
    if search_query:
        all_users = all_users.filter(
            models.Q(username__icontains=search_query) |
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(email__icontains=search_query)
        )
    
    return render(request, 'accounts/user_list.html', {
        'users': all_users,
        'search_query': search_query,
        'role_filter': role_filter,
    })


def register_parents(request):
    if request.user.is_authenticated and request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can register parents.")
        return redirect('dashboard')
    
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone_number')
        id_number=request.POST.get('id_number')


        if not id_number:
            messages.error(request,"ID Number is required for parent registration!")
            return redirect('register_page')
        
        id_number=id_number.strip()

        if User.objects.filter(username=id_number).exists():
            messages.error(request,f"User with ID Number {id_number} already exists!")
            return redirect('register_page')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, f"User with email {email} already exists!")
            return redirect('register_page')
        
        
        
        try:
            user = User.objects.create_user(
                username=id_number,
                email=email,
                password=settings.DEFAULT_PASSWORD,
                first_name=first_name,
                last_name=last_name,
                role='PARENT',
                phone_number=phone,
                is_approved=True
            )
            messages.success(request, f"Parent {first_name} {last_name} registered successfully!")
            messages.info(request, f"Username: {id_number} | Password: {settings.DEFAULT_PASSWORD}")  # ← CHANGE THIS
            messages.warning(request, "Please inform the parent to change their password on first login.")
            return redirect('user_list')
        except Exception as e:
            messages.error(request, f"Error creating parent: {e}")
    
    return render(request, 'accounts/register_form.html')


@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(old_password):
            messages.error(request, "Current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        elif len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, "Password changed successfully! Please login again.")
            return redirect('login')
    
    return render(request, 'accounts/change_password.html')


@login_required
def delete_user(request, user_id):
    """Delete a user - Only Super Admin"""
    if request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can delete users.")
        return redirect('user_list')
    
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if user_to_delete.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('user_list')
    
    username = user_to_delete.username
    
    if user_to_delete.role == 'STUDENT':
        Students.objects.filter(user=user_to_delete).delete()
    elif user_to_delete.role == 'TEACHER':
        Teacher.objects.filter(user=user_to_delete).delete()
    
    user_to_delete.delete()
    
    messages.success(request, f"User '{username}' has been deleted successfully!")
    return redirect('user_list')


def register_page(request):
    """One page for all registrations - Student, Teacher, Parent"""
    from academic.models import Classroom, Subject
    from accounts.models import User
    
    if request.user.is_authenticated and request.user.role != 'SUPER_ADMIN':
        messages.error(request, "Only Super Admin can register users.")
        return redirect('dashboard')
    
    context = {
        'classrooms': Classroom.objects.all(),
        'subjects': Subject.objects.all(),
        'parents': User.objects.filter(role='PARENT'),
    }
    return render(request, 'accounts/register_form.html', context)