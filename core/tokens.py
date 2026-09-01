from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


class AccessAccountAccessToken(AccessToken):
    pass


class AccessAccountRefreshToken(RefreshToken):
    access_token_class = AccessAccountAccessToken

    @classmethod
    def for_access_account(cls, access_account):
        token = cls()
        token[api_settings.USER_ID_CLAIM] = str(access_account.pk)
        token["person_id"] = access_account.person_id
        token["must_change_password"] = access_account.must_change_password
        return token
