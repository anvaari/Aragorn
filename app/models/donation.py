from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ArtistClaim(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64)
    bio: str = Field(default="", max_length=500)
    ton_address: str = ""  # GRAM wallet (user-friendly EQ…/UQ… form)
    evm_address: str = ""  # Base wallet receiving USDC


class StarsDonation(BaseModel):
    amount: int = Field(ge=1, le=10000)


class GramDonation(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=9)


class UsdcDonation(BaseModel):
    tx_hash: str = Field(pattern=r"^0x[0-9a-fA-F]{64}$")
