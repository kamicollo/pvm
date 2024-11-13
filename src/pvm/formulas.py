import ibis
from ibis import deferred as col


def derive_effect_fields(
    field, start: str, end: str, expr_prefix=1
) -> list[ibis.Deferred]:
    fields = []
    if field.rate and field.quantity:
        quantity_change = (
            col[field.quantity.name + "_" + end]
            - col[field.quantity.name + "_" + start]
        )
        rate_change = (
            col[field.rate.name + "_" + end] - col[field.rate.name + "_" + start]
        )
        fields.append(rate_change.name(field.rate.name + "_change_" + start))
        fields.append(quantity_change.name(field.quantity.name + "_change_" + start))
        fields.append(
            ibis.case()
            .when(
                (col[field.quantity.name + "_" + end] != 0)
                & (col[field.quantity.name + "_" + start] != 0),
                quantity_change * col[field.rate.name + "_" + end] * expr_prefix,
            )
            .else_(quantity_change * expr_prefix)
            .end()
            .name(field.quantity.name + "_effect_" + start)
        )

        if field.quantity.components:
            fields.extend(
                derive_effect_fields(
                    field.quantity,
                    start,
                    end,
                    expr_prefix * (col[field.rate.name + "_" + end]),
                )
            )

        fields.append(
            ibis.case()
            .when(
                (col[field.quantity.name + "_" + end] != 0)
                & (col[field.quantity.name + "_" + start] != 0),
                rate_change * col[field.quantity.name + "_" + start] * expr_prefix,
            )
            .else_(0)
            .end()
            .name(field.rate.name + "_effect_" + start)
        )

        if field.rate.components:
            fields.extend(
                derive_effect_fields(
                    field.rate,
                    start,
                    end,
                    expr_prefix * (col[field.quantity.name + "_" + start]),
                )
            )

    for f in field.other_components:
        fields.append(
            ((col[f.name + "_" + end] - col[f.name + "_" + start]) * expr_prefix).name(
                f.name + "_effect_" + start
            )
        )
    return fields
