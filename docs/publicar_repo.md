# Antes de hacer público el repo

El repo es **privado** hoy. Al pasarlo a público se publica **todo el histórico**, no el
estado final: cualquier cosa que haya estado en un commit queda visible para siempre. Por
eso la limpieza se hace **una sola vez, justo antes de publicar**, y no a trocitos.

## La regla

1. **Nada de datos personales** en ficheros trackeados: ni notas reales de los formularios,
   ni nombres de personas, ni valores de salud concretos. Auditado el 2026-08-24: limpio,
   y ningún fichero ignorado (`.env`, `health-boost-*.json`, `keep.txt`, `jarvis.db`) se
   coló nunca en la historia.
2. **No identificar cuáles son los dos equipos.** Que el proyecto se desarrolla en dos
   máquinas y se sincroniza por git es información técnica necesaria y se queda; a qué
   corresponde cada una, no, y basta con "el otro equipo" / "un segundo equipo". El árbol de
   trabajo ya está así, pero el **histórico** conserva la redacción vieja: eso es lo que
   arregla la receta de abajo.

## Checklist

- [ ] **Pushear desde las DOS máquinas.** Es el bloqueante: si una tiene commits sin
      pushear, la reescritura los deja colgando de una historia que ya no existe.
- [ ] Repasar `git log -p` buscando datos personales que se hayan colado desde la última
      auditoría.
- [ ] **Borrar este fichero** (contiene las cadenas a purgar, ver aviso abajo).
- [ ] Ejecutar la reescritura (abajo).
- [ ] `git push --force` y **volver a clonar en las dos máquinas**. Los hashes cambian, así
      que un `pull` normal no vale.
- [ ] Recordar que `.env`, `health-boost-*.json`, `keep.txt` y `jarvis.db` siguen fuera del
      repo y se pasan a mano.

## La reescritura

`git filter-repo` no viene instalado: `pip install git-filter-repo`. Trabaja mejor sobre un
clon recién hecho.

> **Ojo con este mismo fichero.** La lista de abajo contiene literalmente las cadenas que
> se están purgando, así que **hay que borrar `docs/publicar_repo.md` (o vaciar la lista)
> en el último commit antes del force-push**. Mientras el repo sea privado no pasa nada;
> publicado, reintroduciría justo lo que la reescritura quita.

Fichero `reemplazos.txt` (fuera del repo, p.ej. en `/tmp`):

```
un segundo equipo==>un segundo equipo
otro equipo==>otro equipo
el otro equipo cae a la voz del navegador==>el otro equipo cae a la voz del navegador
(otro equipo / apagado)==>(otro equipo / apagado)
keep del otro equipo==>keep del otro equipo
En el otro equipo solo==>En el otro equipo solo
a qué corresponde cada una==>a qué corresponde cada una
no, y basta con "el otro equipo". En el árbol==>no, y basta con "el otro equipo". En el árbol
"<términos que identifiquen las máquinas>"==>"<términos que identifiquen las máquinas>"
Daniel==>Marta
daniel==>marta
el primo de Soria==>la del coro
```

**Los nombres de personas.** El árbol de trabajo ya no tiene ninguno (barrido el
2026-11-11: el entrenador pasó a ser "el entrenador" y los ejemplos del prompt usan un
nombre inventado), pero el histórico conserva el nombre real de un tercero, su parentesco
y su ciudad. De ahí las tres líneas de arriba. **El nombre del propio Hugo se queda a
propósito**: es el autor, firma cada commit y el repo cuelga de su cuenta; lo que no debe
leerse como suyo es la APLICACIÓN, y eso se arregla hablando de "el usuario" en el código
y los mensajes de commit, no borrándole la autoría.

Las dos líneas del bloque que empiezan por `que una de ellas` y por `"<términos>` existen
porque este mismo fichero llegó a contener esas frases en los commits del 2026-08-24,
antes de reescribirlo.

```bash
git clone https://github.com/Hugo966/health_booster.git limpio && cd limpio
git filter-repo --replace-text /tmp/reemplazos.txt
git remote add origin https://github.com/Hugo966/health_booster.git
git push --force origin main
```

Comprobación de que no queda nada:

```bash
git log --all -p --pretty=format: | grep -inE "<términos que identifiquen las máquinas>" || echo limpio
# (ojo: este grep también casa consigo mismo dentro de este fichero)
```

Las seis líneas de arriba cubren las **diez variantes** que había en el histórico el
2026-08-24. Si entre medias se escribe alguna nueva, volver a enumerarlas con ese mismo
`grep` sobre `git log -p` antes de lanzar la reescritura.

## Qué SÍ conviene que se publique

El `README.md` es la carta de presentación, en inglés, y va con las cifras medidas. El
análisis de `docs/app_movil.md` sobre qué haría falta para comercializar (multiusuario,
autenticación, RGPD art. 9) se deja a propósito: enseña que los límites del sistema están
identificados, que es lo que se lee bien en un repo de portfolio.
