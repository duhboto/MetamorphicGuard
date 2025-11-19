# Branch Protection Rules for Releases

## Recommended Settings for `main` Branch

### Basic Protection (Essential)

**Ruleset Name:** `main-branch-protection`

**Target Branches:**
- Branch name pattern: `main`
- Or: `main`, `master` (if you use master)

**Rules to Enable:**

1. ✅ **Restrict deletions**
   - Prevents accidental deletion of the main branch

2. ✅ **Block force pushes**
   - Prevents rewriting history on main branch
   - Critical for release stability

3. ✅ **Require linear history**
   - Ensures clean, linear commit history
   - Makes releases easier to track

4. ✅ **Require a pull request before merging**
   - All changes must go through PR review
   - Configure:
     - ✅ Require approvals: **1** (or more)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
     - ✅ Require review from Code Owners (if you have CODEOWNERS file)

5. ✅ **Require status checks to pass**
   - Select these checks (based on your workflows):
     - `test` (from `.github/workflows/test.yml`)
     - `type-check` (if you have it)
     - `security-scan` (from test.yml)
   - ✅ Require branches to be up to date before merging

6. ✅ **Require deployments to succeed** (Optional)
   - Only if you have deployment environments set up
   - Usually not needed for library releases

### Advanced Protection (Recommended)

7. ✅ **Require signed commits** (Optional but recommended)
   - Ensures all commits are verified
   - Requires GPG key setup for all contributors

8. ✅ **Restrict creations** (Optional)
   - Only allow bypass users to create branches matching main
   - Prevents accidental branch creation

9. ✅ **Restrict updates** (Optional)
   - Only allow bypass users to update main directly
   - Forces all changes through PRs

### Bypass List

**Who should have bypass permissions:**
- Repository administrators (you)
- CI/CD bots (GitHub Actions)
- Release automation tools

**Note:** Be careful with bypass permissions - only grant to trusted automation and administrators.

## Quick Setup Checklist

- [ ] Create ruleset named `main-branch-protection`
- [ ] Target branch: `main`
- [ ] Enable: Restrict deletions
- [ ] Enable: Block force pushes
- [ ] Enable: Require linear history
- [ ] Enable: Require pull request before merging
  - [ ] Require 1 approval minimum
  - [ ] Dismiss stale approvals
- [ ] Enable: Require status checks to pass
  - [ ] Select `test` workflow
  - [ ] Select `security-scan` workflow
  - [ ] Require branches to be up to date
- [ ] Add yourself to bypass list (for emergency fixes)
- [ ] Save ruleset

## For Release Tags

**Note:** Tags themselves don't need protection rules, but you can:
1. Protect tags in repository settings → Tags
2. Require signed tags for releases
3. Restrict tag creation to administrators

## Testing Your Protection

After setting up:
1. Try to push directly to main (should fail)
2. Create a PR and ensure tests pass
3. Verify you can't force push
4. Confirm releases can only be created from protected main branch

