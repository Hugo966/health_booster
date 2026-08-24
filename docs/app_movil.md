# App móvil — plan y pasos previos

Estado: **sin empezar**. Este documento existe para poder retomarlo en el portátil sin
tener que reconstruir las decisiones. El motor que la app va a consumir (API de
formularios, semáforo y herramientas de voz de Jarvis) está **terminado y en `main`**
desde el 2026-08-24.

## Qué hacer nada más llegar al portátil

1. **`git pull --rebase`.** Hay un commit local sin pushear en ese equipo desde antes.
   Los commits de formularios no tocan `status_pipeline.py` ni `entreno_pipeline.py`, que
   es donde probablemente estén esos cambios, así que debería entrar limpio.
2. **Actualizar el `keep.txt`** si sigue desincronizado. No va por git; el bueno es el que
   tenga las sesiones más recientes. El panel de Formularios lo detecta solo y avisa en
   ámbar (compara el keep local con `entreno_sesion` de la hoja).
3. **Montar Tailscale** (abajo).

## Tailscale — cómo llega el móvil al backend

Decidido el 2026-08-24. La alternativa era abrir el backend a la wifi con
`--host 0.0.0.0`, y se descartó: expondría a cualquiera de la red unos endpoints que
**escriben** en la hoja. Con `tailscale serve` el backend sigue escuchando **solo en
localhost** y solo se llega desde la red privada de Hugo, además con HTTPS de verdad.
Por eso **`run.sh` no hay que tocarlo**.

En la máquina que corra el backend (el portátil):

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up            # imprime una URL: abrirla y entrar con Google/GitHub
sudo tailscale serve --bg 8099
```

El último comando devuelve una dirección `https://<equipo>.<tailnet>.ts.net`. **Esa es la
que va en `API_BASE` de la app.** Puede pedir activar MagicDNS y HTTPS en la consola web
de Tailscale la primera vez.

En el móvil: instalar **Tailscale desde Play Store** y entrar con la misma cuenta.

Nota: Tailscale es para uso personal. **Si esto llega a venderse, no sirve** —a un cliente
no se le puede pedir que instale una VPN— y el backend tendría que vivir en la nube, con
autenticación y multiusuario. Ver "Sobre comercializar" abajo.

## Decisiones ya tomadas (no volver a plantearlas)

| Decisión | Elegido | Por qué |
|---|---|---|
| Tecnología | **Expo / React Native**, no PWA | La voz. `voz.ts` no se porta: `webkitSpeechRecognition` no existe en iOS y es flaky en Chrome Android, el wake word por polling se come la batería y el SO mata el micro en segundo plano, y el TTS apunta a `localhost:8123`. Una PWA/TWA llegaría a Play Store pero sin voz, que es lo que hace a Jarvis Jarvis. |
| Alcance v1 | **Formularios + Jarvis por voz** | Es lo que se usa de verdad en el móvil y reaprovecha entera la API existente. |
| Alcance final | Todo, **presentado de otra forma** | Los 7 paneles no se calcan en una pantalla de móvil. La arquitectura se deja preparada para que quepan sin rehacer. |
| Plataforma | **Android** para probar, ambas como meta | Publicar en iOS son 99 $/año y hace falta un Mac para compilar. Expo cubre las dos, así que no atarse a módulos solo-Android. |
| Red | **Tailscale** | Ver arriba. |

## Qué se reaprovecha y qué hay que rehacer

**Tal cual**: toda la API de formularios (`/formulario/{tipo}`, `/formularios/estado`,
`/formularios/esquema`), `lib/chat.ts` completo (el SSE por `fetch`+reader funciona con
`expo/fetch`), `lib/acciones.ts` y `lib/formularios.ts`.

**Regalo gratis**: `SESION_FIJA = "hugo"` (`chat.ts:58`) más el polling de `GET /hilo` cada
3 s hacen que la app comparta hilo con el escritorio sin escribir una línea.

**Hay que rehacer**: `voz.ts` entera (STT nativo + Porcupine para el wake word), los
gráficos cuando toquen (Recharts no existe en RN) y `Presencia.tsx` sobre Skia.

## Trampas conocidas

- **Porcupine y casi cualquier módulo nativo de audio NO funcionan en Expo Go.** Hacen
  falta *development builds* (compilar tu propia app). No impide empezar, pero la primera
  versión con voz real ya pasa por ahí.
- **El micro NO exige HTTPS en app nativa**, al contrario que en el navegador. Eso quita
  de encima el problema que empujaba a Tailscale durante el desarrollo; Tailscale se queda
  por poder usarla fuera de casa y por no abrir el backend a la wifi.
- **Picovoice necesita una clave** (gratis) para el wake word, y el keyword de fábrica es
  inglés: quizá haya que entrenar uno con la pronunciación española de Hugo.
- **Google Play Developer son 25 $, pago único.** Solo para publicar, no para desarrollar.

## Sobre comercializar

Conviene tenerlo escrito para que no condicione mal las decisiones del día a día. El
sistema es **monousuario hasta el tuétano**: una sola hoja de Google, un service account,
la sesión `"hugo"` cableada, sin autenticación, y un modelo de datos atado al keep de Hugo
y al Excel de su entrenador. Venderlo significa multiusuario con autenticación,
almacenamiento por usuario (Sheets no sirve de base de datos multiusuario) y datos de
salud, que en el RGPD son **categoría especial** (art. 9) con obligaciones propias. Es otro
producto sobre las mismas ideas, no una fase más.

Lo que sí se ha hecho es dejarlo encaminado: los formularios están detrás de una **API HTTP
limpia** que consumen por igual el PC y el móvil, en vez de que cada cliente hable con la
hoja por su cuenta.
