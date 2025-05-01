from django import forms
from .models import DevFile

class DevFileForm(forms.ModelForm):
    class Meta:
        model = DevFile
        fields = ['file']
