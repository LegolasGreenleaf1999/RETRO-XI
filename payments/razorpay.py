import razorpay
from django.conf import settings 
client=razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_KEY_SECRET))
def create_razorpay_order(amount,receipt): 
    data={
        'amount':int(amount*100),
        'currency':'INR',
        'receipt':receipt, 
        'payment_capture':1
    }
    return client.order.create(data=data)