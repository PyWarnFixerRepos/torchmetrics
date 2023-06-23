# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Optional

import torch
from torch import Tensor
from typing_extensions import Literal

from torchmetrics.functional.classification.stat_scores import (
    _binary_stat_scores_arg_validation,
    _binary_stat_scores_format,
    _binary_stat_scores_tensor_validation,
    _binary_stat_scores_update,
    _multiclass_stat_scores_arg_validation,
    _multiclass_stat_scores_format,
    _multiclass_stat_scores_tensor_validation,
    _multiclass_stat_scores_update,
    _multilabel_stat_scores_arg_validation,
    _multilabel_stat_scores_format,
    _multilabel_stat_scores_tensor_validation,
    _multilabel_stat_scores_update,
    _reduce_stat_scores,
)
from torchmetrics.utilities.compute import _safe_divide
from torchmetrics.utilities.enums import AverageMethod as AvgMethod
from torchmetrics.utilities.enums import MDMCAverageMethod


def _fbeta_reduce(
    tp: Tensor,
    fp: Tensor,
    tn: Tensor,
    fn: Tensor,
    beta: float,
    average: Optional[Literal["binary", "micro", "macro", "weighted", "none"]],
    multidim_average: Literal["global", "samplewise"] = "global",
) -> Tensor:
    beta2 = beta**2
    if average == "binary":
        return _safe_divide((1 + beta2) * tp, (1 + beta2) * tp + beta2 * fn + fp)
    elif average == "micro":
        tp = tp.sum(dim=0 if multidim_average == "global" else 1)
        fn = fn.sum(dim=0 if multidim_average == "global" else 1)
        fp = fp.sum(dim=0 if multidim_average == "global" else 1)
        return _safe_divide((1 + beta2) * tp, (1 + beta2) * tp + beta2 * fn + fp)
    else:
        fbeta_score = _safe_divide((1 + beta2) * tp, (1 + beta2) * tp + beta2 * fn + fp)
        if average is None or average == "none":
            return fbeta_score
        if average == "weighted":
            weights = tp + fn
        else:
            weights = torch.ones_like(fbeta_score)
        return _safe_divide(weights * fbeta_score, weights.sum(-1, keepdim=True)).sum(-1)


def _binary_fbeta_score_arg_validation(
    beta: float,
    threshold: float = 0.5,
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
) -> None:
    if not (isinstance(beta, float) and beta > 0):
        raise ValueError(f"Expected argument `beta` to be a float larger than 0, but got {beta}.")
    _binary_stat_scores_arg_validation(threshold, multidim_average, ignore_index)


def binary_fbeta_score(
    preds: Tensor,
    target: Tensor,
    beta: float,
    threshold: float = 0.5,
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes `F-score`_ metric for binary tasks:

    .. math::
        F_{\beta} = (1 + \beta^2) * \frac{\text{precision} * \text{recall}}
        {(\beta^2 * \text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds`` (int or float tensor): ``(N, ...)``. If preds is a floating point tensor with values outside
      [0,1] range we consider the input to be logits and will auto apply sigmoid per element. Addtionally,
      we convert to int tensor with thresholding using the value in ``threshold``.
    - ``target`` (int tensor): ``(N, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        beta: Weighting between precision and recall in calculation. Setting to 1 corresponds to equal weight
        threshold: Threshold for transforming probability to binary {0,1} predictions
        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        If ``multidim_average`` is set to ``global``, the metric returns a scalar value. If ``multidim_average``
        is set to ``samplewise``, the metric returns ``(N,)`` vector consisting of a scalar value per sample.

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import binary_fbeta_score
        >>> target = torch.tensor([0, 1, 0, 1, 0, 1])
        >>> preds = torch.tensor([0, 0, 1, 1, 0, 1])
        >>> binary_fbeta_score(preds, target, beta=2.0)
        tensor(0.6667)

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import binary_fbeta_score
        >>> target = torch.tensor([0, 1, 0, 1, 0, 1])
        >>> preds = torch.tensor([0.11, 0.22, 0.84, 0.73, 0.33, 0.92])
        >>> binary_fbeta_score(preds, target, beta=2.0)
        tensor(0.6667)

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import binary_fbeta_score
        >>> target = torch.tensor([[[0, 1], [1, 0], [0, 1]], [[1, 1], [0, 0], [1, 0]]])
        >>> preds = torch.tensor(
        ...     [
        ...         [[0.59, 0.91], [0.91, 0.99], [0.63, 0.04]],
        ...         [[0.38, 0.04], [0.86, 0.780], [0.45, 0.37]],
        ...     ]
        ... )
        >>> binary_fbeta_score(preds, target, beta=2.0, multidim_average='samplewise')
        tensor([0.5882, 0.0000])
    """
    if validate_args:
        _binary_fbeta_score_arg_validation(beta, threshold, multidim_average, ignore_index)
        _binary_stat_scores_tensor_validation(preds, target, multidim_average, ignore_index)
    preds, target = _binary_stat_scores_format(preds, target, threshold, ignore_index)
    tp, fp, tn, fn = _binary_stat_scores_update(preds, target, multidim_average)
    return _fbeta_reduce(tp, fp, tn, fn, beta, average="binary", multidim_average=multidim_average)


def _multiclass_fbeta_score_arg_validation(
    beta: float,
    num_classes: int,
    top_k: int = 1,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
) -> None:
    if not (isinstance(beta, float) and beta > 0):
        raise ValueError(f"Expected argument `beta` to be a float larger than 0, but got {beta}.")
    _multiclass_stat_scores_arg_validation(num_classes, top_k, average, multidim_average, ignore_index)


def multiclass_fbeta_score(
    preds: Tensor,
    target: Tensor,
    beta: float,
    num_classes: int,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    top_k: int = 1,
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes `F-score`_ metric for multiclass tasks:

    .. math::
        F_{\beta} = (1 + \beta^2) * \frac{\text{precision} * \text{recall}}
        {(\beta^2 * \text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds``: ``(N, ...)`` (int tensor) or ``(N, C, ..)`` (float tensor). If preds is a floating point
      we apply ``torch.argmax`` along the ``C`` dimension to automatically convert probabilities/logits into
      an int tensor.
    - ``target`` (int tensor): ``(N, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        beta: Weighting between precision and recall in calculation. Setting to 1 corresponds to equal weight
        num_classes: Integer specifing the number of classes
        average:
            Defines the reduction that is applied over labels. Should be one of the following:

            - ``micro``: Sum statistics over all labels
            - ``macro``: Calculate statistics for each label and average them
            - ``weighted``: Calculates statistics for each label and computes weighted average using their support
            - ``"none"`` or ``None``: Calculates statistic for each label and applies no reduction
        top_k:
            Number of highest probability or logit score predictions considered to find the correct label.
            Only works when ``preds`` contain probabilities/logits.
        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        The returned shape depends on the ``average`` and ``multidim_average`` arguments:

        - If ``multidim_average`` is set to ``global``:

          - If ``average='micro'/'macro'/'weighted'``, the output will be a scalar tensor
          - If ``average=None/'none'``, the shape will be ``(C,)``

        - If ``multidim_average`` is set to ``samplewise``:

          - If ``average='micro'/'macro'/'weighted'``, the shape will be ``(N,)``
          - If ``average=None/'none'``, the shape will be ``(N, C)``

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import multiclass_fbeta_score
        >>> target = torch.tensor([2, 1, 0, 0])
        >>> preds = torch.tensor([2, 1, 0, 1])
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3)
        tensor(0.7963)
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3, average=None)
        tensor([0.5556, 0.8333, 1.0000])

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import multiclass_fbeta_score
        >>> target = torch.tensor([2, 1, 0, 0])
        >>> preds = torch.tensor([
        ...   [0.16, 0.26, 0.58],
        ...   [0.22, 0.61, 0.17],
        ...   [0.71, 0.09, 0.20],
        ...   [0.05, 0.82, 0.13],
        ... ])
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3)
        tensor(0.7963)
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3, average=None)
        tensor([0.5556, 0.8333, 1.0000])

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import multiclass_fbeta_score
        >>> target = torch.tensor([[[0, 1], [2, 1], [0, 2]], [[1, 1], [2, 0], [1, 2]]])
        >>> preds = torch.tensor([[[0, 2], [2, 0], [0, 1]], [[2, 2], [2, 1], [1, 0]]])
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3, multidim_average='samplewise')
        tensor([0.4697, 0.2706])
        >>> multiclass_fbeta_score(preds, target, beta=2.0, num_classes=3, multidim_average='samplewise', average=None)
        tensor([[0.9091, 0.0000, 0.5000],
                [0.0000, 0.3571, 0.4545]])
    """
    if validate_args:
        _multiclass_fbeta_score_arg_validation(beta, num_classes, top_k, average, multidim_average, ignore_index)
        _multiclass_stat_scores_tensor_validation(preds, target, num_classes, multidim_average, ignore_index)
    preds, target = _multiclass_stat_scores_format(preds, target, top_k)
    tp, fp, tn, fn = _multiclass_stat_scores_update(
        preds, target, num_classes, top_k, average, multidim_average, ignore_index
    )
    return _fbeta_reduce(tp, fp, tn, fn, beta, average=average, multidim_average=multidim_average)


def _multilabel_fbeta_score_arg_validation(
    beta: float,
    num_labels: int,
    threshold: float = 0.5,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
) -> None:
    if not (isinstance(beta, float) and beta > 0):
        raise ValueError(f"Expected argument `beta` to be a float larger than 0, but got {beta}.")
    _multilabel_stat_scores_arg_validation(num_labels, threshold, average, multidim_average, ignore_index)


def multilabel_fbeta_score(
    preds: Tensor,
    target: Tensor,
    beta: float,
    num_labels: int,
    threshold: float = 0.5,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes `F-score`_ metric for multilabel tasks:

    .. math::
        F_{\beta} = (1 + \beta^2) * \frac{\text{precision} * \text{recall}}
        {(\beta^2 * \text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds`` (int or float tensor): ``(N, C, ...)``. If preds is a floating point tensor with values outside
      [0,1] range we consider the input to be logits and will auto apply sigmoid per element. Addtionally,
      we convert to int tensor with thresholding using the value in ``threshold``.
    - ``target`` (int tensor): ``(N, C, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        beta: Weighting between precision and recall in calculation. Setting to 1 corresponds to equal weight
        num_labels: Integer specifing the number of labels
        threshold: Threshold for transforming probability to binary (0,1) predictions
        average:
            Defines the reduction that is applied over labels. Should be one of the following:

            - ``micro``: Sum statistics over all labels
            - ``macro``: Calculate statistics for each label and average them
            - ``weighted``: Calculates statistics for each label and computes weighted average using their support
            - ``"none"`` or ``None``: Calculates statistic for each label and applies no reduction

        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        The returned shape depends on the ``average`` and ``multidim_average`` arguments:

        - If ``multidim_average`` is set to ``global``:

          - If ``average='micro'/'macro'/'weighted'``, the output will be a scalar tensor
          - If ``average=None/'none'``, the shape will be ``(C,)``

        - If ``multidim_average`` is set to ``samplewise``:

          - If ``average='micro'/'macro'/'weighted'``, the shape will be ``(N,)``
          - If ``average=None/'none'``, the shape will be ``(N, C)``

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import multilabel_fbeta_score
        >>> target = torch.tensor([[0, 1, 0], [1, 0, 1]])
        >>> preds = torch.tensor([[0, 0, 1], [1, 0, 1]])
        >>> multilabel_fbeta_score(preds, target, beta=2.0, num_labels=3)
        tensor(0.6111)
        >>> multilabel_fbeta_score(preds, target, beta=2.0, num_labels=3, average=None)
        tensor([1.0000, 0.0000, 0.8333])

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import multilabel_fbeta_score
        >>> target = torch.tensor([[0, 1, 0], [1, 0, 1]])
        >>> preds = torch.tensor([[0.11, 0.22, 0.84], [0.73, 0.33, 0.92]])
        >>> multilabel_fbeta_score(preds, target, beta=2.0, num_labels=3)
        tensor(0.6111)
        >>> multilabel_fbeta_score(preds, target, beta=2.0, num_labels=3, average=None)
        tensor([1.0000, 0.0000, 0.8333])

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import multilabel_fbeta_score
        >>> target = torch.tensor([[[0, 1], [1, 0], [0, 1]], [[1, 1], [0, 0], [1, 0]]])
        >>> preds = torch.tensor(
        ...     [
        ...         [[0.59, 0.91], [0.91, 0.99], [0.63, 0.04]],
        ...         [[0.38, 0.04], [0.86, 0.780], [0.45, 0.37]],
        ...     ]
        ... )
        >>> multilabel_fbeta_score(preds, target, num_labels=3, beta=2.0, multidim_average='samplewise')
        tensor([0.5556, 0.0000])
        >>> multilabel_fbeta_score(preds, target, num_labels=3, beta=2.0, multidim_average='samplewise', average=None)
        tensor([[0.8333, 0.8333, 0.0000],
                [0.0000, 0.0000, 0.0000]])
    """
    if validate_args:
        _multilabel_fbeta_score_arg_validation(beta, num_labels, threshold, average, multidim_average, ignore_index)
        _multilabel_stat_scores_tensor_validation(preds, target, num_labels, multidim_average, ignore_index)
    preds, target = _multilabel_stat_scores_format(preds, target, num_labels, threshold, ignore_index)
    tp, fp, tn, fn = _multilabel_stat_scores_update(preds, target, multidim_average)
    return _fbeta_reduce(tp, fp, tn, fn, beta, average=average, multidim_average=multidim_average)


def binary_f1_score(
    preds: Tensor,
    target: Tensor,
    threshold: float = 0.5,
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes F-1 score for binary tasks:

    .. math::
        F_{1} = 2\frac{\text{precision} * \text{recall}}{(\text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds`` (int or float tensor): ``(N, ...)``. If preds is a floating point tensor with values outside
      [0,1] range we consider the input to be logits and will auto apply sigmoid per element. Addtionally,
      we convert to int tensor with thresholding using the value in ``threshold``.
    - ``target`` (int tensor): ``(N, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        threshold: Threshold for transforming probability to binary {0,1} predictions
        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        If ``multidim_average`` is set to ``global``, the metric returns a scalar value. If ``multidim_average``
        is set to ``samplewise``, the metric returns ``(N,)`` vector consisting of a scalar value per sample.

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import binary_f1_score
        >>> target = torch.tensor([0, 1, 0, 1, 0, 1])
        >>> preds = torch.tensor([0, 0, 1, 1, 0, 1])
        >>> binary_f1_score(preds, target)
        tensor(0.6667)

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import binary_f1_score
        >>> target = torch.tensor([0, 1, 0, 1, 0, 1])
        >>> preds = torch.tensor([0.11, 0.22, 0.84, 0.73, 0.33, 0.92])
        >>> binary_f1_score(preds, target)
        tensor(0.6667)

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import binary_f1_score
        >>> target = torch.tensor([[[0, 1], [1, 0], [0, 1]], [[1, 1], [0, 0], [1, 0]]])
        >>> preds = torch.tensor(
        ...     [
        ...         [[0.59, 0.91], [0.91, 0.99], [0.63, 0.04]],
        ...         [[0.38, 0.04], [0.86, 0.780], [0.45, 0.37]],
        ...     ]
        ... )
        >>> binary_f1_score(preds, target, multidim_average='samplewise')
        tensor([0.5000, 0.0000])
    """
    return binary_fbeta_score(
        preds=preds,
        target=target,
        beta=1.0,
        threshold=threshold,
        multidim_average=multidim_average,
        ignore_index=ignore_index,
        validate_args=validate_args,
    )


def multiclass_f1_score(
    preds: Tensor,
    target: Tensor,
    num_classes: int,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    top_k: int = 1,
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes F-1 score for multiclass tasks:

    .. math::
        F_{1} = 2\frac{\text{precision} * \text{recall}}{(\text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds``: ``(N, ...)`` (int tensor) or ``(N, C, ..)`` (float tensor). If preds is a floating point
      we apply ``torch.argmax`` along the ``C`` dimension to automatically convert probabilities/logits into
      an int tensor.
    - ``target`` (int tensor): ``(N, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        num_classes: Integer specifing the number of classes
        average:
            Defines the reduction that is applied over labels. Should be one of the following:

            - ``micro``: Sum statistics over all labels
            - ``macro``: Calculate statistics for each label and average them
            - ``weighted``: Calculates statistics for each label and computes weighted average using their support
            - ``"none"`` or ``None``: Calculates statistic for each label and applies no reduction
        top_k:
            Number of highest probability or logit score predictions considered to find the correct label.
            Only works when ``preds`` contain probabilities/logits.
        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        The returned shape depends on the ``average`` and ``multidim_average`` arguments:

        - If ``multidim_average`` is set to ``global``:

          - If ``average='micro'/'macro'/'weighted'``, the output will be a scalar tensor
          - If ``average=None/'none'``, the shape will be ``(C,)``

        - If ``multidim_average`` is set to ``samplewise``:

          - If ``average='micro'/'macro'/'weighted'``, the shape will be ``(N,)``
          - If ``average=None/'none'``, the shape will be ``(N, C)``

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import multiclass_f1_score
        >>> target = torch.tensor([2, 1, 0, 0])
        >>> preds = torch.tensor([2, 1, 0, 1])
        >>> multiclass_f1_score(preds, target, num_classes=3)
        tensor(0.7778)
        >>> multiclass_f1_score(preds, target, num_classes=3, average=None)
        tensor([0.6667, 0.6667, 1.0000])

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import multiclass_f1_score
        >>> target = torch.tensor([2, 1, 0, 0])
        >>> preds = torch.tensor([
        ...   [0.16, 0.26, 0.58],
        ...   [0.22, 0.61, 0.17],
        ...   [0.71, 0.09, 0.20],
        ...   [0.05, 0.82, 0.13],
        ... ])
        >>> multiclass_f1_score(preds, target, num_classes=3)
        tensor(0.7778)
        >>> multiclass_f1_score(preds, target, num_classes=3, average=None)
        tensor([0.6667, 0.6667, 1.0000])

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import multiclass_f1_score
        >>> target = torch.tensor([[[0, 1], [2, 1], [0, 2]], [[1, 1], [2, 0], [1, 2]]])
        >>> preds = torch.tensor([[[0, 2], [2, 0], [0, 1]], [[2, 2], [2, 1], [1, 0]]])
        >>> multiclass_f1_score(preds, target, num_classes=3, multidim_average='samplewise')
        tensor([0.4333, 0.2667])
        >>> multiclass_f1_score(preds, target, num_classes=3, multidim_average='samplewise', average=None)
        tensor([[0.8000, 0.0000, 0.5000],
                [0.0000, 0.4000, 0.4000]])
    """
    return multiclass_fbeta_score(
        preds=preds,
        target=target,
        beta=1.0,
        num_classes=num_classes,
        average=average,
        top_k=top_k,
        multidim_average=multidim_average,
        ignore_index=ignore_index,
        validate_args=validate_args,
    )


def multilabel_f1_score(
    preds: Tensor,
    target: Tensor,
    num_labels: int,
    threshold: float = 0.5,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "macro",
    multidim_average: Literal["global", "samplewise"] = "global",
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes F-1 score for multilabel tasks:

    .. math::
        F_{1} = 2\frac{\text{precision} * \text{recall}}{(\text{precision}) + \text{recall}}

    Accepts the following input tensors:

    - ``preds`` (int or float tensor): ``(N, C, ...)``. If preds is a floating point tensor with values outside
      [0,1] range we consider the input to be logits and will auto apply sigmoid per element. Addtionally,
      we convert to int tensor with thresholding using the value in ``threshold``.
    - ``target`` (int tensor): ``(N, C, ...)``

    The influence of the additional dimension ``...`` (if present) will be determined by the `multidim_average`
    argument.

    Args:
        preds: Tensor with predictions
        target: Tensor with true labels
        num_labels: Integer specifing the number of labels
        threshold: Threshold for transforming probability to binary (0,1) predictions
        average:
            Defines the reduction that is applied over labels. Should be one of the following:

            - ``micro``: Sum statistics over all labels
            - ``macro``: Calculate statistics for each label and average them
            - ``weighted``: Calculates statistics for each label and computes weighted average using their support
            - ``"none"`` or ``None``: Calculates statistic for each label and applies no reduction

        multidim_average:
            Defines how additionally dimensions ``...`` should be handled. Should be one of the following:

            - ``global``: Additional dimensions are flatted along the batch dimension
            - ``samplewise``: Statistic will be calculated independently for each sample on the ``N`` axis.
              The statistics in this case are calculated over the additional dimensions.

        ignore_index:
            Specifies a target value that is ignored and does not contribute to the metric calculation
        validate_args: bool indicating if input arguments and tensors should be validated for correctness.
            Set to ``False`` for faster computations.

    Returns:
        The returned shape depends on the ``average`` and ``multidim_average`` arguments:

        - If ``multidim_average`` is set to ``global``:

          - If ``average='micro'/'macro'/'weighted'``, the output will be a scalar tensor
          - If ``average=None/'none'``, the shape will be ``(C,)``

        - If ``multidim_average`` is set to ``samplewise``:

          - If ``average='micro'/'macro'/'weighted'``, the shape will be ``(N,)``
          - If ``average=None/'none'``, the shape will be ``(N, C)``

    Example (preds is int tensor):
        >>> from torchmetrics.functional.classification import multilabel_f1_score
        >>> target = torch.tensor([[0, 1, 0], [1, 0, 1]])
        >>> preds = torch.tensor([[0, 0, 1], [1, 0, 1]])
        >>> multilabel_f1_score(preds, target, num_labels=3)
        tensor(0.5556)
        >>> multilabel_f1_score(preds, target, num_labels=3, average=None)
        tensor([1.0000, 0.0000, 0.6667])

    Example (preds is float tensor):
        >>> from torchmetrics.functional.classification import multilabel_f1_score
        >>> target = torch.tensor([[0, 1, 0], [1, 0, 1]])
        >>> preds = torch.tensor([[0.11, 0.22, 0.84], [0.73, 0.33, 0.92]])
        >>> multilabel_f1_score(preds, target, num_labels=3)
        tensor(0.5556)
        >>> multilabel_f1_score(preds, target, num_labels=3, average=None)
        tensor([1.0000, 0.0000, 0.6667])

    Example (multidim tensors):
        >>> from torchmetrics.functional.classification import multilabel_f1_score
        >>> target = torch.tensor([[[0, 1], [1, 0], [0, 1]], [[1, 1], [0, 0], [1, 0]]])
        >>> preds = torch.tensor(
        ...     [
        ...         [[0.59, 0.91], [0.91, 0.99], [0.63, 0.04]],
        ...         [[0.38, 0.04], [0.86, 0.780], [0.45, 0.37]],
        ...     ]
        ... )
        >>> multilabel_f1_score(preds, target, num_labels=3, multidim_average='samplewise')
        tensor([0.4444, 0.0000])
        >>> multilabel_f1_score(preds, target, num_labels=3, multidim_average='samplewise', average=None)
        tensor([[0.6667, 0.6667, 0.0000],
                [0.0000, 0.0000, 0.0000]])
    """
    return multilabel_fbeta_score(
        preds=preds,
        target=target,
        beta=1.0,
        num_labels=num_labels,
        threshold=threshold,
        average=average,
        multidim_average=multidim_average,
        ignore_index=ignore_index,
        validate_args=validate_args,
    )


def _fbeta_compute(
    tp: Tensor,
    fp: Tensor,
    tn: Tensor,
    fn: Tensor,
    beta: float,
    ignore_index: Optional[int],
    average: str,
    mdmc_average: Optional[str],
) -> Tensor:
    """Computes f_beta metric from stat scores: true positives, false positives, true negatives, false negatives.

    Example:
        >>> from torchmetrics.functional.classification.stat_scores import _stat_scores_update
        >>> target = torch.tensor([0, 1, 2, 0, 1, 2])
        >>> preds = torch.tensor([0, 2, 1, 0, 0, 1])
        >>> tp, fp, tn, fn = _stat_scores_update(preds, target, reduce='micro', num_classes=3)
        >>> _fbeta_compute(tp, fp, tn, fn, beta=0.5, ignore_index=None, average='micro', mdmc_average=None)
        tensor(0.3333)
    """
    if average == AvgMethod.MICRO and mdmc_average != MDMCAverageMethod.SAMPLEWISE:
        mask = tp >= 0
        precision = _safe_divide(tp[mask].sum().float(), (tp[mask] + fp[mask]).sum())
        recall = _safe_divide(tp[mask].sum().float(), (tp[mask] + fn[mask]).sum())
    else:
        precision = _safe_divide(tp.float(), tp + fp)
        recall = _safe_divide(tp.float(), tp + fn)

    num = (1 + beta**2) * precision * recall
    denom = beta**2 * precision + recall
    denom[denom == 0.0] = 1.0  # avoid division by 0

    # if classes matter and a given class is not present in both the preds and the target,
    # computing the score for this class is meaningless, thus they should be ignored
    if average == AvgMethod.NONE and mdmc_average != MDMCAverageMethod.SAMPLEWISE:
        # a class is not present if there exists no TPs, no FPs, and no FNs
        meaningless_indeces = torch.nonzero((tp | fn | fp) == 0).cpu()
        if ignore_index is None:
            ignore_index = meaningless_indeces
        else:
            ignore_index = torch.unique(torch.cat((meaningless_indeces, torch.tensor([[ignore_index]]))))

    if ignore_index is not None:
        if average not in (AvgMethod.MICRO, AvgMethod.SAMPLES) and mdmc_average == MDMCAverageMethod.SAMPLEWISE:
            num[..., ignore_index] = -1
            denom[..., ignore_index] = -1
        elif average not in (AvgMethod.MICRO, AvgMethod.SAMPLES):
            num[ignore_index, ...] = -1
            denom[ignore_index, ...] = -1

    if average == AvgMethod.MACRO and mdmc_average != MDMCAverageMethod.SAMPLEWISE:
        cond = (tp + fp + fn == 0) | (tp + fp + fn == -3)
        num = num[~cond]
        denom = denom[~cond]

    return _reduce_stat_scores(
        numerator=num,
        denominator=denom,
        weights=None if average != AvgMethod.WEIGHTED else tp + fn,
        average=average,
        mdmc_average=mdmc_average,
    )


def fbeta_score(
    preds: Tensor,
    target: Tensor,
    task: Literal["binary", "multiclass", "multilabel"],
    beta: float = 1.0,
    threshold: float = 0.5,
    num_classes: Optional[int] = None,
    num_labels: Optional[int] = None,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "micro",
    multidim_average: Optional[Literal["global", "samplewise"]] = "global",
    top_k: Optional[int] = 1,
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes `F-score`_ metric:

    .. math::
        F_{\beta} = (1 + \beta^2) * \frac{\text{precision} * \text{recall}}
        {(\beta^2 * \text{precision}) + \text{recall}}

    This function is a simple wrapper to get the task specific versions of this metric, which is done by setting the
    ``task`` argument to either ``'binary'``, ``'multiclass'`` or ``multilabel``. See the documentation of
    :func:`binary_fbeta_score`, :func:`multiclass_fbeta_score` and :func:`multilabel_fbeta_score` for the specific
    details of each argument influence and examples.

    Legacy Example:
        >>> target = torch.tensor([0, 1, 2, 0, 1, 2])
        >>> preds = torch.tensor([0, 2, 1, 0, 0, 1])
        >>> fbeta_score(preds, target, task="multiclass", num_classes=3, beta=0.5)
        tensor(0.3333)
    """
    assert multidim_average is not None
    if task == "binary":
        return binary_fbeta_score(preds, target, beta, threshold, multidim_average, ignore_index, validate_args)
    if task == "multiclass":
        assert isinstance(num_classes, int)
        assert isinstance(top_k, int)
        return multiclass_fbeta_score(
            preds, target, beta, num_classes, average, top_k, multidim_average, ignore_index, validate_args
        )
    if task == "multilabel":
        assert isinstance(num_labels, int)
        return multilabel_fbeta_score(
            preds, target, beta, num_labels, threshold, average, multidim_average, ignore_index, validate_args
        )
    raise ValueError(
        f"Expected argument `task` to either be `'binary'`, `'multiclass'` or `'multilabel'` but got {task}"
    )


def f1_score(
    preds: Tensor,
    target: Tensor,
    task: Literal["binary", "multiclass", "multilabel"],
    threshold: float = 0.5,
    num_classes: Optional[int] = None,
    num_labels: Optional[int] = None,
    average: Optional[Literal["micro", "macro", "weighted", "none"]] = "micro",
    multidim_average: Optional[Literal["global", "samplewise"]] = "global",
    top_k: Optional[int] = 1,
    ignore_index: Optional[int] = None,
    validate_args: bool = True,
) -> Tensor:
    r"""Computes F-1 score:

    .. math::
        F_{1} = 2\frac{\text{precision} * \text{recall}}{(\text{precision}) + \text{recall}}

    This function is a simple wrapper to get the task specific versions of this metric, which is done by setting the
    ``task`` argument to either ``'binary'``, ``'multiclass'`` or ``multilabel``. See the documentation of
    :func:`binary_f1_score`, :func:`multiclass_f1_score` and :func:`multilabel_f1_score` for the specific
    details of each argument influence and examples.

    Legacy Example:
        >>> target = torch.tensor([0, 1, 2, 0, 1, 2])
        >>> preds = torch.tensor([0, 2, 1, 0, 0, 1])
        >>> f1_score(preds, target, task="multiclass", num_classes=3)
        tensor(0.3333)
    """
    assert multidim_average is not None
    if task == "binary":
        return binary_f1_score(preds, target, threshold, multidim_average, ignore_index, validate_args)
    if task == "multiclass":
        assert isinstance(num_classes, int)
        assert isinstance(top_k, int)
        return multiclass_f1_score(
            preds, target, num_classes, average, top_k, multidim_average, ignore_index, validate_args
        )
    if task == "multilabel":
        assert isinstance(num_labels, int)
        return multilabel_f1_score(
            preds, target, num_labels, threshold, average, multidim_average, ignore_index, validate_args
        )
    raise ValueError(
        f"Expected argument `task` to either be `'binary'`, `'multiclass'` or `'multilabel'` but got {task}"
    )
