# Contributing to DM4PRICE

## Branch Strategy

- `main` is always the stable branch.
- `develop` is the working integration branch.
- Create feature branches from `develop`.

Use branch names like:

- `feature/discovery-improvements`
- `feature/seller-analytics`
- `fix/login-validation`
- `hotfix/payment-checkout`

## Recommended Workflow

1. Start from the latest `develop`.
2. Create a new branch for your change.
3. Keep commits focused and readable.
4. Run tests before opening a pull request.
5. Open a pull request into `develop`.
6. After review and testing, merge `develop` into `main` for release.

## Commands

Create a feature branch:

```powershell
git checkout develop
git pull
git checkout -b feature/my-change
```

Push a branch:

```powershell
git push -u origin feature/my-change
```

Update your branch with the latest `develop`:

```powershell
git checkout develop
git pull
git checkout feature/my-change
git merge develop
```

## Pull Request Checklist

- The app runs locally.
- Relevant tests pass.
- No secrets or local-only files were committed.
- The change is described clearly in the pull request.
- Screenshots are included for UI changes when useful.
