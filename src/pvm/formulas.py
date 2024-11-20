"""Formulas for PVM."""

import ibis
from ibis import deferred as col

from pvm import CHANGE_COLUMN, EFFECT_COLUMN
from pvm.fields import CompositeRateField, Field, QuantityField, RateField


def change_field(field: Field | QuantityField | RateField | CompositeRateField, start: str, end: str) -> ibis.Deferred:
    """
    Derive change expression for a field.

    Args:
        field (Field | QuantityField | RateField | CompositeRateField): The field to derive changes for.
        start (str): The start period.
        end (str): The end period.

    Returns:
        ibis.Deferred: Expression for the change field.

    """
    return (col[field.name + "_" + end] - col[field.name + "_" + start]).name(
        field.name + CHANGE_COLUMN + start,
    )


def derive_effect_fields(
    field: RateField | QuantityField | Field,
    start: str,
    end: str,
    expr_prefix: float | ibis.Deferred = 1.0,
) -> list[ibis.Deferred]:
    """
    Derive effect fields for a field.

    Args:
        field (RateField | QuantityField | Field): The field to derive effects for.
        start (str): The start period.
        end (str): The end period.
        expr_prefix (int | ibis.Deferred, optional): The expression prefix. Defaults to 1.

    Returns:
        list[ibis.Deferred]: The derived effect fields.

    """
    fields = []

    if field.rate and field.quantity:
        quantity_start = col[field.quantity.name + "_" + start]
        rate_start = col[field.rate.name + "_" + start]
        quantity_end = col[field.quantity.name + "_" + end]
        rate_end = col[field.rate.name + "_" + end]
        quantity_change = quantity_end - quantity_start
        rate_change = rate_end - rate_start
        calculation_condition = (quantity_start != 0) & (quantity_end != 0)

        fields.append(
            ibis.case()
            .when(
                calculation_condition,
                quantity_change * rate_start * expr_prefix,
            )
            .else_(quantity_change * expr_prefix)
            .end()
            .name(field.quantity.name + EFFECT_COLUMN + start),
        )

        if field.quantity.components:
            fields.extend(
                derive_effect_fields(
                    field.quantity,
                    start,
                    end,
                    expr_prefix * rate_start,
                ),
            )

        fields.append(
            ibis.case()
            .when(
                calculation_condition,
                rate_change * quantity_end * expr_prefix,
            )
            .else_(0)
            .end()
            .name(field.rate.name + EFFECT_COLUMN + start),
        )

        if field.rate.components:
            fields.extend(
                derive_effect_fields(
                    field.rate,
                    start,
                    end,
                    expr_prefix * quantity_end * ibis.case().when(calculation_condition, 1).else_(0).end(),
                ),
            )

    fields.extend(
        [
            ((col[f.name + "_" + end] - col[f.name + "_" + start]) * expr_prefix).name(
                f.name + EFFECT_COLUMN + start,
            )
            for f in field.other_components
        ],
    )
    return fields
