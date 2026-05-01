from __future__ import annotations

from fastapi import APIRouter, Request

from web_service.services.validation_cases import (
    build_profile_from_required_params,
    convert_float_value,
    convert_int_value,
    get_missing_user_email,
    get_none_email_lowercase,
    normalize_username,
    parse_age_param,
    parse_date_value,
    query_page,
    read_age_from_body,
)


router = APIRouter(tags=["extra-bug-cases"])


@router.get("/validation/missing-required")
async def missing_required(request: Request) -> dict[str, object]:
    return build_profile_from_required_params(dict(request.query_params))


@router.get("/validation/bad-age")
async def bad_age(request: Request) -> dict[str, int]:
    return parse_age_param(dict(request.query_params))


@router.get("/validation/bad-range")
async def bad_range(request: Request) -> dict[str, object]:
    return query_page(dict(request.query_params))


@router.get("/validation/empty-username")
async def empty_username(request: Request) -> dict[str, str]:
    return normalize_username(dict(request.query_params))


@router.get("/nulls/missing-user")
async def missing_user() -> dict[str, str]:
    return get_missing_user_email()


@router.get("/nulls/none-email")
async def none_email() -> dict[str, str]:
    return get_none_email_lowercase()


@router.post("/body/missing-age")
async def missing_body_age(request: Request) -> dict[str, int]:
    data = await request.json()
    return read_age_from_body(data)


@router.get("/conversion/int-string")
async def int_string(value: str) -> dict[str, int]:
    return convert_int_value(value)


@router.get("/conversion/float-string")
async def float_string(value: str) -> dict[str, float]:
    return convert_float_value(value)


@router.get("/conversion/bad-date")
async def bad_date(date: str) -> dict[str, str]:
    return parse_date_value(date)
