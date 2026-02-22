# GitHub Pages Setup (No Actions)

This setup publishes docs from a branch/folder and does not require GitHub Actions.

## Preconditions

- Repository is pushed to GitHub.
- Documentation files are in `docs/`.
- Entry page is `docs/index.md`.

## GitHub UI Steps

1. Open repository `Settings`.
2. Open `Pages`.
3. Under `Build and deployment`:
   - `Source`: **Deploy from a branch**
   - `Branch`: `main`
   - `Folder`: `/docs`
4. Click `Save`.

GitHub will build and publish the site directly from `docs/`.

## Expected URL

- User/organization site pattern:
  - `https://<owner>.github.io/<repo>/`

## Updating Docs

- Edit files under `docs/`.
- Commit and push to `main`.
- GitHub Pages republish happens automatically from the branch source.

## Troubleshooting

- If site is not updating, verify Pages source is still `main` + `/docs`.
- If Markdown renders but styling is minimal, that is expected for default Jekyll theme.
- If you renamed the default branch, update Pages branch selection.
