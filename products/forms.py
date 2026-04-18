from django import forms
from .models import Product, ProductImage, ProductRating, SellerRating, ProductReport, SellerReport

class ProductForm(forms.ModelForm):
    """Form for adding/editing products"""
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'price', 'is_negotiable', 'whatsapp_number', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Detailed product description',
                'rows': 5
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 25000 (leave blank for "Contact for price")',
                'min': '0',
                'step': '0.01',
            }),
            'is_negotiable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+2348012345678'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }


class ProductImageForm(forms.ModelForm):
    """Form for uploading product images"""
    is_primary = forms.BooleanField(
        required=False,
        label='Set as primary image',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = ProductImage
        fields = ['image', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }


class ProductRatingForm(forms.ModelForm):
    """Form for rating a product"""
    score = forms.ChoiceField(
        choices=[(i, f'⭐ {i} star{"s" if i != 1 else ""}') for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'rating-radio'}),
        label='Rate this product'
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Share your experience with this product (optional)',
            'rows': 3,
        }),
        label='Write a review (optional)'
    )

    class Meta:
        model = ProductRating
        fields = ['score', 'comment']


class SellerRatingForm(forms.ModelForm):
    """Form for rating a seller"""
    score = forms.ChoiceField(
        choices=[(i, f'⭐ {i} star{"s" if i != 1 else ""}') for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'rating-radio'}),
        label='Rate this seller'
    )
    
    class Meta:
        model = SellerRating
        fields = ['score']


class ProductReportForm(forms.ModelForm):
    """Form for reporting a product"""
    reason = forms.ChoiceField(
        choices=ProductReport.REASON_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'report-radio'}),
        label='Why are you reporting this product?'
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Provide details about why you are reporting this product...',
            'rows': 4
        }),
        label='Additional details'
    )
    
    class Meta:
        model = ProductReport
        fields = ['reason', 'description']


class SellerReportForm(forms.ModelForm):
    """Form for reporting a seller"""
    reason = forms.ChoiceField(
        choices=SellerReport.REASON_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'report-radio'}),
        label='Why are you reporting this seller?'
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Provide details about why you are reporting this seller...',
            'rows': 4
        }),
        label='Additional details'
    )
    
    class Meta:
        model = SellerReport
        fields = ['reason', 'description']
