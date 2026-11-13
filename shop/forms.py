
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=160)
    email = forms.EmailField()
    phone = forms.CharField(
        max_length=10,
        error_messages={
            "required": "Phone number must contain exactly 10 digits.",
            "max_length": "Phone number must contain exactly 10 digits.",
        },
        widget=forms.TextInput(attrs={
            "inputmode": "numeric",
            "autocomplete": "tel",
            "pattern": "[0-9]{10}",
            "title": "Phone number must contain exactly 10 digits.",
        }),
    )
    address = forms.CharField(
        error_messages={
            "required": (
                "Enter a valid delivery address with at least five letters "
                "and two details (such as a street and number)."
            ),
        },
        widget=forms.Textarea(attrs={
            "rows": 3,
            "minlength": 8,
            "title": (
                "Enter a valid delivery address with at least five letters "
                "and two details (such as a street and number)."
            ),
        }),
    )

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if not phone.isascii() or not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError(
                "Phone number must contain exactly 10 digits."
            )
        return phone

    def clean_address(self):
        address = self.cleaned_data["address"].strip()
        address_error = (
            "Enter a valid delivery address with at least five letters "
            "and two details (such as a street and number)."
        )
        words = address.split()
        if (
            len(address) < 8
            or sum(character.isalpha() for character in address) < 5
            or len(words) < 2
            or any(
                not (
                    character.isalpha()
                    or character.isdigit()
                    or character.isspace()
                    or character in ".,#/'()-"
                )
                for character in address
            )
        ):
            raise forms.ValidationError(address_error)
        return address
