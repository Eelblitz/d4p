from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    """Form for user registration"""
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=False, max_length=20)
    is_seller = forms.BooleanField(
        required=False, 
        label="I want to be a seller",
        help_text="Check this if you want to sell products on our marketplace"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'is_seller', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data.get('phone_number')
        if commit:
            user.save()
        return user


class NINVerificationForm(forms.Form):
    nin_number = forms.CharField(
        max_length=11,
        min_length=11,
        label='NIN',
        help_text='Enter your 11-digit National Identification Number for seller approval.',
        widget=forms.TextInput(attrs={'placeholder': '12345678901'}),
    )

    def clean_nin_number(self):
        nin_number = self.cleaned_data['nin_number'].strip()
        if not nin_number.isdigit():
            raise forms.ValidationError('NIN must contain exactly 11 digits.')
        return nin_number


class CustomAuthenticationForm(AuthenticationForm):
    """Form for user login"""
    class Meta:
        model = User
        fields = ('username', 'password')
