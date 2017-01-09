# -*- coding: utf-8 -*-
from __future__ import absolute_import
from itertools import chain
import six
from typing import List

import tabulate

from eli5.base import FeatureImportances
from . import fields
from .features import FormattedFeatureName
from .utils import (
    format_signed, has_any_values_for_weights, replace_spaces,
    should_highlight_spaces)
from .trees import tree2text


_PLUS_MINUS = "+-" if six.PY2 else "±"
_ELLIPSIS = '...' if six.PY2 else '…'
_SPACE = '_' if six.PY2 else '░'


def format_as_text(expl, show=fields.ALL, highlight_spaces=None):
    """ Format explanation as text.
    If ``highlight_spaces`` is None (default), spaces will be highlighted in
    feature names only if there are any spaces at the start or at the end of the
    feature. Setting it to True forces space highlighting, and setting it to False
    turns it off.
    """
    lines = []  # type: List[str]

    if highlight_spaces is None:
        highlight_spaces = should_highlight_spaces(expl)

    if expl.error:  # always shown
        lines.extend(_error_lines(expl))

    for key in show:
        if not getattr(expl, key, None):
            continue

        if key == 'method':
            lines.extend(_method_lines(expl))

        if key == 'description':
            lines.extend(_description_lines(expl))

        if key == 'transition_features':
            lines.extend(_transition_features_lines(expl))

        if key == 'targets':
            lines.extend(_targets_lines(expl, hl_spaces=highlight_spaces))

        if key == 'feature_importances':
            lines.extend(_feature_importances_lines(
                expl, hl_spaces=highlight_spaces))

        if key == 'decision_tree':
            lines.extend(_decision_tree_lines(expl))

    return '\n'.join(lines)


def _method_lines(explanation):
    return ['Explained as: {}'.format(explanation.method)]


def _description_lines(explanation):
    return [explanation.description]


def _error_lines(explanation):
    return ['Error: {}'.format(explanation.error)]


def _feature_importances_lines(explanation, hl_spaces):
    max_width = 0
    for line in _fi_lines(explanation.feature_importances, hl_spaces):
        max_width = max(max_width, len(line))
        yield line
    if explanation.feature_importances.remaining:
        yield _format_remaining(
            explanation.feature_importances.remaining, kind='', width=max_width)


def _fi_lines(feature_importances, hl_spaces):
    for fw in feature_importances.importances:
        featname = _format_feature(fw.feature, hl_spaces)
        if fw.std is None:
            yield u'{w:0.4f}  {feature}'.format(feature=featname, w=fw.weight)
        else:
            yield u'{w:0.4f} {plus} {std:0.4f}  {feature}'.format(
                feature=featname,
                w=fw.weight,
                plus=_PLUS_MINUS,
                std=2 * fw.std,
            )

def _decision_tree_lines(explanation):
    return ["", tree2text(explanation.decision_tree)]


def _transition_features_lines(explanation):
    from tabulate import tabulate  # type: ignore
    tf = explanation.transition_features
    return [
        "",
        "Transition features:",
        tabulate(tf.coef, headers=tf.class_names, showindex=tf.class_names,
                 floatfmt="0.3f"),
        ""
    ]


def _targets_lines(explanation, hl_spaces):
    lines = []
    has_values_for_weights = has_any_values_for_weights(explanation)

    for target in explanation.targets:
        scores = _format_scores(target.proba, target.score)
        if scores:
            scores = " (%s)" % scores

        header = "%s%r%s top features" % (
            'y=' if not explanation.is_regression else '',
            target.target,
            scores)
        lines.append(header)

        if has_values_for_weights:
            table_header = ['Contribution', 'Feature', 'Value']
            table_line = lambda fw: [
                fw.weight, _format_feature(fw.feature, hl_spaces), fw.value]
        else:
            table_header = ['Weight', 'Feature']
            table_line = lambda fw: [
                fw.weight, _format_feature(fw.feature, hl_spaces)]

        w = target.feature_weights
        table = tabulate.tabulate(
            [table_line(fw) for fw in chain(w.pos, w.neg)],
            headers=table_header,
            numalign='right',
            floatfmt='+.3f',
        ).split('\n')
        table = [table[1]] + table  # add extra header separator
        max_width = len(table[0])
        pos_table = '\n'.join(table[:-len(w.neg)])
        neg_table = '\n'.join(table[-len(w.neg):])

        lines.append(pos_table)
        if w.pos_remaining:
            lines.append(
                _format_remaining(w.pos_remaining, 'positive', max_width))
        if w.neg_remaining:
            lines.append(
                _format_remaining(w.neg_remaining, 'negative', max_width))
        lines.append(neg_table)

        lines.append('')
    return lines


def _format_scores(proba, score):
    scores = []
    if proba is not None:
        scores.append("probability=%0.3f" % proba)
    if score is not None:
        scores.append("score=%0.3f" % score)
    return ", ".join(scores)


def _format_feature_weights(feature_weights, sz, hl_spaces):
    return [
        u'{weight:+8.3f}  {feature}'.format(
            weight=fw.weight,
            feature=_format_feature(fw.feature, hl_spaces=hl_spaces).ljust(sz))
        for fw in feature_weights]


def _format_remaining(remaining, kind, width):
    s = '{ellipsis} {remaining} more {kind}{ellipsis}'.format(
        ellipsis=_ELLIPSIS,
        remaining=remaining,
        kind=(kind + ' ') if kind else '',
    )
    return ('{:^%d}' % width).format(s)


def _format_feature(name, hl_spaces):
    if isinstance(name, bytes):
        name = name.decode('utf8')
    if isinstance(name, FormattedFeatureName):
        return name.format()
    elif isinstance(name, list) and \
            all('name' in x and 'sign' in x for x in name):
        return _format_unhashed_feature(name, hl_spaces=hl_spaces)
    else:
        return _format_single_feature(name, hl_spaces=hl_spaces)


def _format_single_feature(feature, hl_spaces):
    if hl_spaces:
        return replace_spaces(feature, lambda n, _: _SPACE * n)
    else:
        return feature


def _format_unhashed_feature(name, hl_spaces, sep=' | '):
    """
    Format feature name for hashed features.
    """
    return sep.join(
        format_signed(n, _format_single_feature, hl_spaces=hl_spaces)
        for n in name)
