from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    """Form for user registration"""
    email = forms.EmailField(required=True)
    is_seller = forms.BooleanField(
        required=False, 
        label="I want to be a seller",
        help_text="Check this if you want to sell products on our marketplace"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'is_seller', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Form for user login"""
    class Meta:
        model = User
        fields = ('username', 'password')
