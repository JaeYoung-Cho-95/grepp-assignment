from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    """커스텀 User 모델을 위한 매니저"""
    
    def create_user(self, email, password, **extra_fields):
        """일반 사용자 생성"""
        if not email:
            raise ValueError('이메일은 필수입니다')
        if not password:
            raise ValueError('비밀번호는 필수입니다')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password, **extra_fields):
        """슈퍼유저 생성"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('슈퍼유저는 is_staff=True여야 합니다')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('슈퍼유저는 is_superuser=True여야 합니다')
        
        return self.create_user(email, password, **extra_fields)