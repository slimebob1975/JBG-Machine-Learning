# Tested versions

`requirements.txt`, `requirements-fastapi.txt` and `requirements-optional-dill.txt`
name the packages JBG needs, without fixed versions (CatBoost has a range).
`constraints-tested.txt` holds the exact versions the gate has passed with, so
that an environment can be reproduced:

```powershell
python -m pip install -r requirements.txt -r requirements-fastapi.txt -c constraints-tested.txt
```

A constraints file only fixes versions. It installs nothing that the
requirements files do not ask for.

## The tested environment (300u, 2026-11-24)

The user's Windows environment, in which the gate passed at 300t (`-Quick`,
1404 tests). Python 3.11 or later: NumPy 2.3 and JAX 0.7 require it. The exact
Python version is recorded at the next update of this file.

| Package | Version | Role |
|---|---|---|
| numpy | 2.3.2 | Numerical core |
| scipy | 1.16.1 | Numerical core |
| pandas | 2.3.1 | Numerical core |
| scikit-learn | 1.7.2 | Numerical core: models, cross-validation, metrics |
| imbalanced-learn | 0.14.0 | Over- and undersampling |
| catboost | 1.2.10 | CatBoost algorithm |
| torch | 2.8.0 | Neural networks (with skorch 1.2.0) |
| tensorflow | 2.20.0 | Neural networks (with keras 3.11.3, scikeras 0.13.0) |
| jax | 0.7.1 | Neural networks (with optax 0.2.6, flax 0.11.2) |
| fastapi | 0.162.0 | Web server (with starlette 0.47.2, pydantic 2.13.5) |
| SQLAlchemy | 2.1.6 | Run store and metadata |
| Jinja2 | 3.1.6 | Web interface templates |
| pyodbc | 5.2.0 | SQL Server |
| pytest | 8.4.2 | Tests |

`constraints-tested.txt` has the full list (40 packages): every package in the
requirements files and the libraries the results depend on (joblib,
threadpoolctl, jaxlib, keras, starlette, pydantic). Windows-only packages such
as pywin32 are left out, so the file also works elsewhere.

## Also passed

The development container (Linux, Python 3.12, with stand-ins for PyTorch,
TensorFlow and JAX) ran the gate up to 300t with newer versions: scikit-learn
1.9.1, pandas 3.0.6, NumPy 2.5.4, SciPy 1.18.1, imbalanced-learn 0.14.2. Two
differences were found and handled:

- scikit-learn 1.9 refuses unregularised QDA on a rank-deficient covariance
  (earlier versions warn). The engine starts QDA regularised. The test accepts
  both since 300s.
- scikit-learn 1.9 refuses the default positive class for averaged precision
  and recall with text classes. The scorers pass no positive class since 300s.
  Average Precision still fails with text classes (BACKLOG).

From 300u the container uses the versions in `constraints-tested.txt` for the
numerical core and the web server, so its gate matches the Windows one.

## Updating

1. Upgrade in a separate environment, or note the current versions first
   (`python -m pip freeze`).
2. Run the full gate (`scripts/run_backend_refactor_tests.ps1`, not `-Quick`).
3. If it passes, write the new versions into `constraints-tested.txt` and this
   file in a revision, with the date, the Python version and the gate result.
4. If it fails, keep the old versions and add the failure to the BACKLOG.
