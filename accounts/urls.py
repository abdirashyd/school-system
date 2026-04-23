
from django.urls import path
from .views import dashboard_view, login_view, register_teacher_view, register_student_view
from .views import user_list_view, admin_reset_password, logout_view, register_parents
from .views import register_page, delete_user, change_password

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register-teacher/', register_teacher_view, name='register_teacher'),
    path('register-student/', register_student_view, name='register_students'),
    path('register-parents/', register_parents, name='register_parents'),
    path('register/', register_page, name='register_page'),  # ← THIS IS THE ONE
    path('user-list/', user_list_view, name='user_list'),
    path('reset-password/<int:user_id>/', admin_reset_password, name='admin_reset_password'),
    path('delete-user/<int:user_id>/', delete_user, name='delete_user'),
    path('change-password/', change_password, name='change_password'),
]