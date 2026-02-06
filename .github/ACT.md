## Run CI locally with 'act'

To run the CI workflow locally using 'act', ensure you have 'act' installed and configured. Then, execute the following command from the root of the repository:
```
act workflow_dispatch -W .github/workflows/ci.yaml --container-architecture linux/amd64 -j checkout-unit-tests
```
