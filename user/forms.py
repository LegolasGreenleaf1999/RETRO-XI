from django import forms 
from django.contrib.auth.models import User   
class SignupForm(forms.ModelForm):
    password1=forms.CharField(widget=forms.PasswordInput)
    password2=forms.CharField(widget=forms.PasswordInput)
    class Meta:
        model=User 
        fields=['first_name','last_name','email']
    def clean(self):
        cleaned=super().clean()  
        if cleaned['password1']!=cleaned['password2']:
            raise forms.ValidationError('Passwords do not match')
        return cleaned
    