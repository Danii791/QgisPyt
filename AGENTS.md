# AGENTS.md — QgisPyt

Aturan wajib untuk segala perubahan pada repo ini.

## Update README.md (WAJIB)

1. Setiap perubahan `README.md` yang akan di-push ke GitHub **wajib dikerjakan dan dikomit dari folder repo ini**:
   `D:\Chepie Rosdian\Documents\VBA Project\Mapping\QgisPyt`
2. **Dilarang** mengubah / meng-commit `README.md` dari folder lain, dan **dilarang** mengedit `README.md` langsung dari GitHub web (github.com). Branch main terlindungi branch protection.
3. Branch `main` dilindungi → setiap perubahan (README maupun script) harus melalui alur **Pull Request**:
   - buat branch baru → commit → `gh pr create` → merge PR (owner Danii791 boleh merge sendiri / bypass persetujuan).
4. `READMELOCAL.md` adalah dokumentasi **lokal** (gitignored) dan **tidak pernah** di-push. Bila `README.md` berubah secara substansial, selaraskan juga `READMELOCAL.md`.
5. Sebelum push / membuat PR: jalankan `git status`, pastikan hanya perubahan yang dimaksud (tidak ada file config `*.txt`, backup, atau `dist/` ikut ter-push).

## Aturan lain

- Jangan menanam kredensial, token, atau password apa pun di repo.
- File `.qgis_log_config.txt` dan `READMELOCAL.md` tidak boleh masuk ke git (sudah di `.gitignore`).