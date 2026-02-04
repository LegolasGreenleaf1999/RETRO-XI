from django import forms 
from product.models import Coupon,Offer,JerseyProduct
class CouponForm(forms.ModelForm):
    class Meta:
        model=Coupon
        fields=[
            'code',
            'discount_type',
            'discount_value',
            'min_order_value',
            'expires_at',
            'is_active'
        ]
        widgets={
            'expires_at':forms.DateTimeInput(
                attrs={'type':'datetime-local'}
            )
        }
class OfferForm(forms.ModelForm):
    class Meta:
        model=Offer
        fields=[
            'name','description','scope',
            'product','category','referral_code',
            'discount_type','discount_value',
            'start_date','end_date','is_active'
        ]
        widgets={
            'start_date':forms.DateInput(attrs={'type':'date','class':'form-control'}),
            'end_date':forms.DateInput(attrs={'type':'date','class':'form-control'}),
        }
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['product'].queryset=JerseyProduct.objects.filter(is_active=True)
    def clean(self):
        cleaned_data=super().clean()
        scope=cleaned_data.get('scope')
        discount_type=cleaned_data.get('discount_type')
        discount_value=cleaned_data.get('discount_value')
        start_date=cleaned_data.get('start_date')
        end_date=cleaned_data.get('end_date')
        if scope=='product' and not cleaned_data.get('product'):
            raise forms.ValidationError('product offer must have a product')
        if scope=='category' and not cleaned_data.get('category'):
            raise forms.ValidationError('category offer must have a category')
        if scope=='referral' and not cleaned_data.get('referral_code'):
            raise forms.ValidationError('referral offer must have a referral code')
        if cleaned_data.get('referral_code'):
            cleaned_data['referral_code']=cleaned_data['referral_code'].strip().upper()
        if discount_value is not None:
            if discount_value<=0:
                raise forms.ValidationError('discount value must be greater than 0')
            if discount_type=='percentage' and discount_value>100:
                raise forms.ValidationError('percentage discount cannot exceed 100%')
        if end_date and start_date and end_date<start_date:
            raise forms.ValidationError('end date cannot be before start date')
        return cleaned_data