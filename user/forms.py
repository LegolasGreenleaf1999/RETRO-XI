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
class ReturnItemForm(forms.Form):
    RETURN_REASONS=[
        ('damaged','Item was damaged'),
        ('wrong_item','Wrong item received'),
        ('size_issue','Size/Fit issue'),
        ('not_as_described','Not as described'),
        ('other','Other'),
    ] 
    reason=forms.ChoiceField(choices=RETURN_REASONS,required=True) 
    notes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':3,'placeholder':'additional details(optional)'}),max_length=500)