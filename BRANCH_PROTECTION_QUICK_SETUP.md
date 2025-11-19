# Quick Branch Protection Setup for Releases

## Step-by-Step Configuration

### 1. Ruleset Name
```
main-branch-protection
```

### 2. Target Branches
- **Branch name pattern:** `main`

### 3. Enable These Rules (Checkboxes)

#### Essential Protection:
- ✅ **Restrict deletions** - Prevents deleting main branch
- ✅ **Block force pushes** - Prevents rewriting history
- ✅ **Require linear history** - Clean commit history
- ✅ **Require a pull request before merging**
  - When enabled, configure:
    - ✅ Require approvals: **1**
    - ✅ Dismiss stale pull request approvals when new commits are pushed
    - ✅ Require review from Code Owners (optional)

#### Status Checks:
- ✅ **Require status checks to pass**
  - Select these status checks:
    - `test` (from test.yml workflow)
    - `security-scan` (from test.yml workflow)
  - ✅ **Require branches to be up to date before merging**

### 4. Bypass List
Add yourself (repository admin) for emergency fixes:
- Your GitHub username
- GitHub Actions (for automated workflows)

### 5. Save the Ruleset

## Status Check Names to Select

Based on your `.github/workflows/test.yml`, these are the job names:
- `test` - Main test suite
- `security-scan` - Security vulnerability scanning

## What This Protects

✅ Releases can only be created from `main` branch  
✅ All changes must go through PR review  
✅ Tests must pass before merging  
✅ No force pushes or history rewriting  
✅ Clean, linear commit history  

## Emergency Bypass

If you need to push directly to main (emergency hotfix):
- You'll need bypass permissions (add yourself to bypass list)
- Or temporarily disable the ruleset

## Testing

After setup, try:
1. Push directly to main → Should be blocked
2. Create a PR → Should require approval and passing tests
3. Try to force push → Should be blocked

