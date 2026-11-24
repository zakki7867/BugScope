"""Unit tests for controlled experiment runner node."""

from unittest.mock import MagicMock
from app.schemas.failure import FailureReport
from app.schemas.hypothesis import RankedHypothesis, EvidenceItem
from app.schemas.reproduction import ReproductionResult
from app.workflow.nodes.experiment_runner import experiment_runner


def test_experiment_runner_confirmed():
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_container.logs.side_effect = [
        b"FAILED tests/test_calc.py::test_price - KeyError: 'price'",
        b"",
    ]
    mock_docker = MagicMock()
    mock_docker.containers.run.return_value = mock_container

    failure_rep = FailureReport(
        error_type="KeyError",
        message="price",
        file="app/calc.py",
        line=10,
        function="calc_price",
        category="KeyError",
    )
    hypotheses = [
        RankedHypothesis(
            id=1,
            title="Missing price key in user dict",
            explanation="Dict has no price key",
            score=1,
            label="supported",
            is_upstream=False,
            rank=1,
            evidence=[],
        )
    ]

    results = experiment_runner(
        repo_dir=".",
        failure_report=failure_rep,
        ranked_hypotheses=hypotheses,
        custom_docker_client=mock_docker,
    )

    assert len(results) == 1
    assert results[0].conclusion == "confirmed"
    assert results[0].success is True
    assert results[0].exit_code == 1


def test_experiment_runner_refuted():
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [
        b"1 passed in 0.05s",
        b"",
    ]
    mock_docker = MagicMock()
    mock_docker.containers.run.return_value = mock_container

    failure_rep = FailureReport(
        error_type="KeyError",
        message="price",
        file="app/calc.py",
        line=10,
        function="calc_price",
        category="KeyError",
    )
    hypotheses = [
        RankedHypothesis(
            id=2,
            title="Alternative theory",
            explanation="Different cause",
            score=0,
            label="unsupported",
            is_upstream=False,
            rank=2,
            evidence=[],
        )
    ]

    results = experiment_runner(
        repo_dir=".",
        failure_report=failure_rep,
        ranked_hypotheses=hypotheses,
        custom_docker_client=mock_docker,
    )

    assert len(results) == 1
    assert results[0].conclusion == "refuted"
    assert results[0].success is False
    assert results[0].exit_code == 0


def test_experiment_runner_docker_unavailable():
    failure_rep = FailureReport(
        error_type="KeyError",
        message="price",
        file="app/calc.py",
        line=10,
        function="calc_price",
        category="KeyError",
    )
    hypotheses = [
        RankedHypothesis(
            id=1,
            title="Missing price key",
            explanation="Dict has no price key",
            score=1,
            label="supported",
            is_upstream=False,
            rank=1,
            evidence=[],
        )
    ]

    # With non-responsive client
    bad_docker = MagicMock()
    bad_docker.ping.side_effect = Exception("Docker daemon down")

    results = experiment_runner(
        repo_dir=".",
        failure_report=failure_rep,
        ranked_hypotheses=hypotheses,
        custom_docker_client=bad_docker,
    )

    assert len(results) == 1
    assert results[0].conclusion == "inconclusive"
    assert results[0].success is False
