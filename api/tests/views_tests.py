import pytest
from unittest.mock import Mock, patch, call

from twilio.rest import Client

from django.contrib.auth.models import User
from model_bakery import baker
from rest_framework.test import APIClient
from phones.models import RealPhone, RelayNumber

from phones.tests.models_tests import make_phone_test_user


@pytest.fixture()
def phone_user():
    yield make_phone_test_user()


@pytest.fixture(autouse=True)
def mocked_twilio_client():
    """
    Mock PhonesConfig with a mock twilio client
    """
    with patch(
        "phones.apps.PhonesConfig.twilio_client", spec_set=Client
    ) as mock_twilio_client:
        yield mock_twilio_client


@pytest.mark.parametrize("format", ("yaml", "json"))
def test_swagger_format(client, format):
    path = f"/api/v1/swagger.{format}"
    response = client.get(path)
    assert response.status_code == 200
    assert response["Content-Type"].startswith(f"application/{format}")


@pytest.mark.parametrize("subpath", ("swagger", "swagger.", "swagger.txt"))
def test_swagger_unknown_format(client, subpath):
    path = f"/api/v1/{subpath}"
    response = client.get(path)
    assert response.status_code == 404


@pytest.mark.django_db
def test_runtime_data(client):
    path = "/api/v1/runtime_data"
    response = client.get(path)
    assert response.status_code == 200


@pytest.mark.parametrize("endpoint", ("realphone", "relaynumber"))
@pytest.mark.django_db
def test_phone_endspoints_require_auth_and_phone_service(endpoint):
    client = APIClient()
    path = f"/api/v1/{endpoint}/"
    response = client.get(path)
    assert response.status_code == 403

    free_user = baker.make(User)
    client.force_authenticate(free_user)
    response = client.get(path)
    assert response.status_code == 403


@pytest.mark.django_db
def test_realphone_get_responds_200(phone_user):
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/realphone/"
    response = client.get(path)
    assert response.status_code == 200


@pytest.mark.django_db
def test_realphone_post_valid_es164_number(phone_user, mocked_twilio_client):
    client = APIClient()
    client.force_authenticate(phone_user)
    number = "+12223334444"
    path = "/api/v1/realphone/"
    data = {"number": number}

    mock_fetch = Mock(return_value=Mock(
        country_code="US", phone_number=number, carrier="verizon"
    ))
    mocked_twilio_client.lookups.v1.phone_numbers = Mock(
        return_value=Mock(fetch=mock_fetch)
    )

    response = client.post(path, data, format='json')
    assert response.status_code == 201
    assert response.data['number'] == number
    assert response.data['verified'] == False
    assert response.data['verification_sent_date'] != ''
    assert "Sent verification" in response.data['message']

    mocked_twilio_client.lookups.v1.phone_numbers.assert_called_once_with(number)
    mock_fetch.assert_called_once()
    mocked_twilio_client.messages.create.assert_called_once()
    call_kwargs = mocked_twilio_client.messages.create.call_args.kwargs
    assert call_kwargs['to'] == number
    assert "verification code" in call_kwargs['body']


@pytest.mark.django_db
def test_realphone_post_valid_verification_code(
    phone_user,
    mocked_twilio_client
):
    number = "+12223334444"
    real_phone = RealPhone.objects.create(user=phone_user, number=number)
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/realphone/"
    data = {
        "number": number, "verification_code": real_phone.verification_code
    }

    mock_fetch = Mock(return_value=Mock(
        country_code="US", phone_number=number, carrier="verizon"
    ))
    mocked_twilio_client.lookups.v1.phone_numbers = Mock(
        return_value=Mock(fetch=mock_fetch)
    )

    response = client.post(path, data, format='json')
    assert response.status_code == 201
    assert response.data['number'] == number
    assert response.data['verified'] == True
    assert response.data['verified_date'] != ''

    mock_fetch.assert_not_called()


@pytest.mark.django_db
def test_realphone_post_invalid_verification_code(
    phone_user,
    mocked_twilio_client
):
    number = "+12223334444"
    real_phone = RealPhone.objects.create(user=phone_user, number=number)
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/realphone/"
    data = {
        "number": number, "verification_code": "not-the-code"
    }

    mock_fetch = Mock(return_value=Mock(
        country_code="US", phone_number=number, carrier="verizon"
    ))
    mocked_twilio_client.lookups.v1.phone_numbers = Mock(
        return_value=Mock(fetch=mock_fetch)
    )

    response = client.post(path, data, format='json')
    assert response.status_code == 400
    real_phone.refresh_from_db()
    assert real_phone.verified == False
    assert real_phone.verified_date == None

    mock_fetch.assert_not_called()


@pytest.mark.django_db
def test_realphone_patch_verification_code(
    phone_user,
    mocked_twilio_client
):
    number = "+12223334444"
    real_phone = RealPhone.objects.create(user=phone_user, number=number)
    client = APIClient()
    client.force_authenticate(phone_user)
    path = f"/api/v1/realphone/{real_phone.id}/"
    data = {
        "number": number, "verification_code": real_phone.verification_code
    }

    mock_fetch = Mock(return_value=Mock(
        country_code="US", phone_number=number, carrier="verizon"
    ))
    mocked_twilio_client.lookups.v1.phone_numbers = Mock(
        return_value=Mock(fetch=mock_fetch)
    )

    response = client.patch(path, data, format='json')
    assert response.status_code == 200
    assert response.data['number'] == number
    assert response.data['verified'] == True
    assert response.data['verified_date'] != ''

    mock_fetch.assert_not_called()


@pytest.mark.django_db
def test_realphone_patch_invalid_verification_code(
    phone_user,
    mocked_twilio_client
):
    number = "+12223334444"
    real_phone = RealPhone.objects.create(user=phone_user, number=number)
    client = APIClient()
    client.force_authenticate(phone_user)
    path = f"/api/v1/realphone/{real_phone.id}/"
    data = {
        "number": number, "verification_code": "not-the-code"
    }

    mock_fetch = Mock(return_value=Mock(
        country_code="US", phone_number=number, carrier="verizon"
    ))
    mocked_twilio_client.lookups.v1.phone_numbers = Mock(
        return_value=Mock(fetch=mock_fetch)
    )

    response = client.patch(path, data, format='json')
    assert response.status_code == 400
    real_phone.refresh_from_db()
    assert real_phone.verified == False
    assert real_phone.verified_date == None

    mock_fetch.assert_not_called()


@pytest.mark.django_db
def test_relaynumber_suggestions_bad_request_for_user_without_real_phone(
    phone_user
):
    real_phone = "+12223334444"
    RealPhone.objects.create(user=phone_user, verified=True, number=real_phone)
    relay_number = "+19998887777"
    RelayNumber.objects.create(user=phone_user, number=relay_number)
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/suggestions/"

    response = client.get(path)

    assert response.status_code == 400


@pytest.mark.django_db
def test_relaynumber_suggestions_bad_request_for_user_already_with_number(
    phone_user
):
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/suggestions/"

    response = client.get(path)

    assert response.status_code == 400


@pytest.mark.django_db
def test_relaynumber_suggestions(phone_user):
    real_phone = "+12223334444"
    RealPhone.objects.create(
        user=phone_user, verified=True, number=real_phone
    )
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/suggestions/"

    response = client.get(path)

    assert response.status_code == 200
    data_keys = list(response.data.keys())
    assert response.data["real_num"] == real_phone
    assert "same_prefix_options" in data_keys
    assert "other_areas_options" in data_keys
    assert "same_area_options" in data_keys


@pytest.mark.django_db
def test_relaynumber_search_requires_param(phone_user):
    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/search/"

    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.django_db
def test_relaynumber_search_by_location(phone_user, mocked_twilio_client):
    mock_list = Mock(return_value=[])
    mocked_twilio_client.available_phone_numbers=Mock(return_value = (
        Mock(local=Mock(list=mock_list))
    ))

    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/search/?location=Miami, FL"

    response = client.get(path)

    assert response.status_code == 200
    available_numbers_calls = (
        mocked_twilio_client.available_phone_numbers.call_args_list
    )
    assert available_numbers_calls == [call("US")]
    assert mock_list.call_args_list == [
        call(in_locality='Miami, FL', limit=10)
    ]


@pytest.mark.django_db
def test_relaynumber_search_by_area_code(phone_user, mocked_twilio_client):
    mock_list = Mock(return_value=[])
    mocked_twilio_client.available_phone_numbers=Mock(return_value = (
        Mock(local=Mock(list=mock_list))
    ))

    client = APIClient()
    client.force_authenticate(phone_user)
    path = "/api/v1/relaynumber/search/?area_code=918"

    response = client.get(path)

    assert response.status_code == 200
    available_numbers_calls = (
        mocked_twilio_client.available_phone_numbers.call_args_list
    )
    assert available_numbers_calls == [call("US")]
    assert mock_list.call_args_list == [
        call(area_code='918', limit=10)
    ]


def test_vcard_no_lookup_key():
    client = APIClient()
    path = "/api/v1/vCard/"

    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.django_db
def test_vcard_wrong_lookup_key():
    client = APIClient()
    path = "/api/v1/vCard/wrong-lookup-key"

    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.django_db
def test_vcard_valid_lookup_key(phone_user):
    real_phone = "+12223334444"
    RealPhone.objects.create(user=phone_user, verified=True, number=real_phone)
    relay_number = "+19998887777"
    relay_number_obj = RelayNumber.objects.create(
        user=phone_user, number=relay_number
    )

    client = APIClient()
    path = f"/api/v1/vCard/{relay_number_obj.vcard_lookup_key}"
    response = client.get(path)

    assert response.status_code == 200
    assert response.data['number'] == relay_number
    assert response.headers['Content-Disposition'] == 'attachment; filename=+19998887777'
