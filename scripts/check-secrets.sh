#!/bin/sh
# Bloque un commit qui contiendrait un fichier .env ou un identifiant.
# Utilisé par .githooks/pre-commit ; peut aussi être lancé à la main : sh scripts/check-secrets.sh

status=0

# 1. Aucun fichier .env réel ne doit être suivi par Git (seul .env.example est autorisé).
for f in $(git diff --cached --name-only --diff-filter=ACMR); do
  case "$(basename "$f")" in
    .env.example) ;;
    .env|.env.*|*.pem|*.key) echo "BLOQUÉ : $f ne doit jamais être commité."; status=1 ;;
  esac
done

# 2. Aucun motif de clé connu dans le contenu ajouté (on affiche le fichier, jamais la valeur).
PATTERNS='sk-ant-[A-Za-z0-9_-]{16,}|xox[abpr]-[A-Za-z0-9-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|secrets\.pursuit\.org/\?'
hits=$(git diff --cached -U0 --diff-filter=ACMR | grep -E '^\+\+\+ b/|^\+' | awk '/^\+\+\+ b\//{file=substr($0,7); next} {print file "\t" $0}' | grep -E "$PATTERNS" | cut -f1 | sort -u)
if [ -n "$hits" ]; then
  echo "BLOQUÉ : identifiant probable dans :"
  echo "$hits" | sed 's/^/  - /'
  status=1
fi

[ $status -eq 0 ] || echo "Retirez l'identifiant (mettez-le dans .env) puis recommencez."
exit $status
