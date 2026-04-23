from django.urls import path
from.import views
urlpatterns=[
    path('teachers/',views.teacher_list,name='teacher_list'),
    path('classroom/',views.classroom_list,name='classroom_list'),
    path('exam/',views.exam_list,name='exam_list'),
    path('results/',views.results,name='results'),
    path('subject/',views.subject_list,name='subject_list'),
    path('classroom/add/', views.add_classroom, name='add_classroom'),
    path('subject/add/', views.add_subject, name='add_subject'),
    path('exam/add/', views.add_exam, name='add_exam'),
    path('results/add/', views.add_results, name='add_results'),
    path('delete-teacher/<int:pk>/', views.delete_teacher, name='delete_teacher'),
    path('schedule/', views.schedule_list, name='schedule_list'),
    path('schedule/add/', views.add_schedule, name='add_schedule'),
    path('schedule/edit/<int:schedule_id>/', views.edit_schedule, name='edit_schedule'),
    path('schedule/delete/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),
]
