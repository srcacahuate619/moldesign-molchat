# Versiones y compatibilidad

MolChat usa versiones SemVer en `pyproject.toml` y `src/molchat_agent/__init__.py`;
ambas deben coincidir. La versión actual del código es 0.1.0: esta página no
afirma que exista una publicación o etiqueta. Mientras la versión mayor sea 0,
una versión menor puede cambiar contratos; los parches se reservan para cambios
compatibles y correcciones. Las fechas de soporte y el compromiso de mantener
versiones antiguas aún no se han establecido; no se promete soporte extendido.

| MolChat | Contrato del sidecar | Estado de MolDesign |
|---|---|---|
| 0.1.0 (código actual) | `moldesign.molchat/1` | Integración probada en un worktree; corte definitivo, instalación limpia y rollback pendientes. La versión exacta de MolDesign compatible aún no está fijada. |

El contrato del sidecar y los endpoints de plataforma son superficies distintas:
la presencia de `/1` no garantiza que la plataforma implemente todas las rutas,
incluidas las propuestas e idempotencia. Véase [contrato](CONTRATO_MOLDESIGN.md).

## Preparar una versión

1. Actualizar ambas versiones y las notas con cambios, migraciones, límites,
   compatibilidad y correcciones de seguridad; identificar la revisión exacta
   de MolDesign efectivamente probada.
2. Ejecutar CI y las pruebas en vivo aplicables. Los skips se informan; no
   cuentan como prueba de compatibilidad. Ensayar instalación limpia y rollback
   antes de declarar soportada la integración de distribución.
3. Desde un commit limpio, generar y verificar el manifiesto vendorizable con
   `scripts/make_manifest.py --write` y `--check`; preservar el hash y el
   commit de origen con los artefactos. Seguir la guía de licencias y procedencia.
4. Crear la etiqueta y publicar los artefactos solo cuando se haya aprobado la
   versión. Una build local o una CI verde no son una release publicada.
