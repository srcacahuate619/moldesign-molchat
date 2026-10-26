# Hoja de ruta — 26 oct. a 4 nov. de 2026

> **Supersedida por `PLAN.md` (Fase 0, 2026-10-26).** Este documento queda como
> registro histórico de la ruta original; la planificación vigente es `PLAN.md`
> (documento interno, excluido del historial público; versión saneada en
> `docs/PLAN_PUBLICO.md` desde la Fase 7).

## Fase 1 — Base entregada

- [x] Nuevo paquete Python independiente y licencia GPL-3.0-or-later (Fase 0).
- [x] Contratos HTTP de lectura y propuesta de docking.
- [x] Planificador opcional con Meta Muse Spark 1.3.
- [x] Ejecución secuencial con aprobación humana por hash.
- [x] Transcripción mediante servicio Whisper local ya existente.
- [x] Reporte estructurado de evidencia y pruebas unitarias aisladas.
- [ ] Validación con un backend MolDesign real (pendiente de entorno de usuario).

## Siguiente iteración (orden estricto)

1. **Compatibilidad:** fijar el commit de MolDesign, ejecutar 10 peticiones de
   contrato y una propuesta aprobada con cuenta de pruebas.
2. **Flujo orquestado:** agregar referencias tipadas a resultados previos y
   estados persistentes `planned/review/approved/running/done/blocked`.
3. **Gate científico:** extender la detención actual por `technical_blockers`
   con políticas por protocolo para `not_evaluated` y advertencias.
4. **Voz Meta opcional:** Muse Voice Transcribe, indicación explícita de salida
   de audio a nube, vocabulario químico; retener Whisper privado como default.
5. **Interfaz:** panel de planes/ejecuciones conectado a `ChatPanel.tsx` sin
   duplicar la UI ni romper MolDesign estable.
6. **Compatibilidad de motores:** conectores para evaluación, batch, reportes,
   preparación y Molcy con APIs versionadas.
7. **Prueba real y demo:** 1 caso público del pipeline M4, comparación con
   resultados del software base, informe con incertidumbres y grabación.

## Puertas de salida antes de competir

- [ ] El equipo verifica aceptación y requisitos oficiales del hackathon.
- [ ] Los commits nuevos (26 oct.–4 nov.) muestran la contribución del evento;
      documentar claramente la base anterior.
- [ ] Sin claves, datos personales, estructuras privadas ni pesos pesados
      incluidos en Git.
- [ ] Tests offline, prueba real con Vina, consentimientos, y validación de
      licencias/dependencias satisfactoria.
- [ ] Nueva URL pública de GitHub y documentación de instalación reproducible.
- [ ] Vídeo breve con flujo completo, fallos controlados y valor científico real.

