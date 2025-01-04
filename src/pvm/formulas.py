"""Formulas for PVM."""

import ibis
from ibis import deferred as col

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
    return (col[field.period_column(end)] - col[field.period_column(start)]).name(
        field.change_column(start),
    )


def _define_rate_and_quantity_effects(
    rate: RateField,
    quantity: QuantityField,
    periods: tuple[str, str],
    expr_prefix: float | ibis.Deferred,
    volume_effect_override: ibis.Deferred | None,
) -> list[ibis.Deferred]:
    """
    Define rate/quantity calculations and propagates them in the graph.

    Args:
        rate (RateField): rate field
        quantity (QuantityField): quantity field
        periods (tuple[str, str]): tuple of start/end periods
        expr_prefix (float | ibis.Deferred): multiplier to apply to effects (defined upstream in the graph)
        volume_effect_override (ibis.Deferred | None): volume effect override (defined upstream in the graph)

    Returns:
        list[ibis.Deferred]: a list of ibis expressions defining calculations.

    """
    start, end = periods
    effects = []
    quantity_start = col[quantity.period_column(start)]
    rate_start = col[rate.period_column(start)]
    quantity_end = col[quantity.period_column(end)]
    rate_end = col[rate.period_column(end)]
    quantity_change = quantity_end - quantity_start
    rate_change = rate_end - rate_start
    calculation_condition = (quantity_start.fill_null(0) != 0) & (quantity_end.fill_null(0) != 0)
    total_change = (quantity_end * rate_end) - (quantity_start * rate_start)

    # add quantity effect
    effects.append(
        ibis.case()
        .when(
            calculation_condition,
            quantity_change * rate_start * expr_prefix,
        )
        .else_(total_change * expr_prefix if volume_effect_override is None else volume_effect_override)
        .end()
        .name(quantity.effect_column(start)),
    )

    # add rate effect
    effects.append(
        ibis.case()
        .when(
            calculation_condition,
            rate_change * quantity_end * expr_prefix,
        )
        .else_(0)
        .end()
        .name(rate.effect_column(start)),
    )

    # if the rate field is composite, also add individual component effects
    if isinstance(rate, CompositeRateField):
        for rate_component in rate.rates:
            rate_component_start = col[rate_component.name + "_" + start]
            rate_component_end = col[rate_component.name + "_" + end]
            rate_component_change = rate_component_end - rate_component_start
            effects.append(
                ibis.case()
                .when(
                    calculation_condition,
                    rate_component_change * quantity_end * expr_prefix,
                )
                .else_(0)
                .end()
                .name(rate_component.effect_column(start)),
            )

    # propagate recursively to any components of quantity fields
    if quantity.components:
        effects.extend(
            derive_effect_fields(
                quantity,
                start,
                end,
                ibis.case().when(calculation_condition, expr_prefix * rate_start).else_(1).end(),  # type: ignore
                total_change if volume_effect_override is None else volume_effect_override,
            ),
        )

    # propagate recursively to any components of rate field
    if rate.components:
        effects.extend(
            derive_effect_fields(
                rate,
                start,
                end,
                ibis.case().when(calculation_condition, expr_prefix * quantity_end).else_(0).end(),  # type: ignore
                None,
            ),
        )
    # propagate recursively to any components of composite rate fields
    if isinstance(rate, CompositeRateField):
        for r in rate.rates:
            if r.components:
                effects.extend(
                    derive_effect_fields(
                        r,
                        start,
                        end,
                        ibis.case().when(calculation_condition, expr_prefix * quantity_end).else_(0).end(),  # type: ignore
                        None,
                    ),
                )

    return effects


def derive_effect_fields(
    field: RateField | QuantityField | Field,
    start: str,
    end: str,
    expr_prefix: float | ibis.Deferred = 1.0,
    volume_effect_override: ibis.Deferred | None = None,
) -> list[ibis.Deferred]:
    """
    Derive effect fields for a field.

    Args:
        field (RateField | QuantityField | Field): The field to derive effects for.
        start (str): The start period.
        end (str): The end period.
        expr_prefix (int | ibis.Deferred, optional): The expression prefix. Defaults to 1.
        volume_effect_override (ibis.Deferred | None, optional): The effect override. Defaults to None.

    Returns:
        list[ibis.Deferred]: The derived effect fields.

    """
    fields = []

    # if the field has a rate and quantity component, calculate price/volume effects
    # and recursively propagate downwards
    if field.rate and field.quantity:
        fields.extend(
            _define_rate_and_quantity_effects(
                field.rate,
                field.quantity,
                (start, end),
                expr_prefix,
                volume_effect_override,
            ),
        )

    # deal with any non-quantity/non-rate components
    for f in field.other_components:
        # add a direct change calculation
        fields.append(
            ((col[f.name + "_" + end] - col[f.name + "_" + start]) * expr_prefix).name(
                f.effect_column(start),
            ),
        )
        # recursively propagate if any components exist
        if f.components:
            fields.extend(
                derive_effect_fields(
                    f,
                    start,
                    end,
                    expr_prefix,
                    None,
                ),
            )
    return fields
