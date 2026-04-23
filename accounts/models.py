from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self,email,username,password=None,**extra_fields):
        if not email:
            raise ValueError("The Email field must be set!")
        email=self.normalize_email(email)
        user=self.model(email=email,username=username,**extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self,email,username,password=None,**extra_fields):
        extra_fields.setdefault('is_staff',True)
        extra_fields.setdefault('is_superuser',True)

        extra_fields.setdefault('role','SUPER_ADMIN')
        extra_fields.setdefault('is_approved',True)

        return self.create_user(email,username,password,**extra_fields)
    
class User(AbstractUser):
    ROLE_CHOICES=(
        ('SUPER_ADMIN','super_Admin'),
        ('ADMIN','admin'),
        ('TEACHER','teacher'),
        ('STUDENT','student'),
        ('PARENT','parent')
    )
    objects=UserManager()

    role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='STUDENT')
    is_approved= models.BooleanField(default=False)
    phone_number=models.CharField(max_length=15,unique=True,null=True,blank=True)

    def __str__(self):
        return f"{self.username}({self.get_role_display()})"
    