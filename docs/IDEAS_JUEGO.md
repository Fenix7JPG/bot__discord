# Ideas y reglas del juego de economía

Reconstrucción organizada de legacy/info.txt, legacy/Chambas.txt y del
comportamiento real implementado en los cogs.

## Niveles de trabajo y sueldos

| Nivel | Rango de sueldo | Ejemplos |
| --- | --- | --- |
| mediocre | 5 a 100 | Recogedor de basura, lavaplatos, DJ amateur |
| bajo | 100 a 150 | Guardia de seguridad, panadero, mecánico |
| medio | 150 a 230 | Policía, bombero, programador, taquero |
| alto | 230 a 500 | Astronauta, cirujano, empresario, rey |

El catálogo completo (101 trabajos) vive en datos/trabajos.json con slug,
nombre, emoji, nivel, experiencia requerida y sueldo. Se regenera con
`python scripts/generar_trabajos.py`.

## Ciclo de juego

1. /jugar: crea el perfil (dinero 0, XP 0, salud 100).
2. /trabajos: revisa la lista y sus requisitos de XP.
3. /postularse-trabajo: si tu XP alcanza el requisito te aceptan seguro; si
   no, tienes un 30% de suerte.
4. /work: ganas sueldo del trabajo (con variación aleatoria x0.9 a x1.3) más
   XP (5-20 + mitad de la XP requerida del puesto). Cooldown de 24 horas.
5. Si trabajas antes de las 24h:
   - Probabilidad de enfermarte: crece linealmente de 5% (a las 23h) a 45%
     (inmediato). Fórmula: max(5, min(45, int((24 - horas) * 45 / 24))).
   - Enfermarte cuesta salud (según la enfermedad), un gasto médico de hasta
     el 10% de tu dinero y solo un cuarto de la XP.
   - Si no te enfermas: pago y XP a la mitad por cansancio.
6. Las enfermedades se curan con /curarse (pagando) o solas a los 3 días.
7. /stats muestra tu progreso.

## Enfermedades

datos/enfermedades.json define 10 enfermedades con severidad, daño de salud,
días de duración y costo de tratamiento. El trabajo adelantado usa una muestra
aleatoria; /curarse cobra según la vida recuperada: costo = hp * 5 + hp^2 *
0.20 (curar mucho cuesta progresivamente más).

## Datos

- La base local `datos/bot.db` ya fue migrada a Turso (perfiles, ranking y
  configuración del servidor) y la carpeta `datos/` se eliminó: todo dato del
  juego vive en la BD.
- Los catálogos de contenido (trabajos, enfermedades) también son tablas de
  la BD; su definición generadora vive en `database/catalogos.py` y se
  siembra sola en el primer arranque.

## Ideas pendientes (del info.txt original)

- Sistema de "slut" mencionado en info.txt sin especificar: no se implementó.
  Interpretación razonable pendiente de definir con el dueño del bot.
- Despido o rebaja de 15% del sueldo si no trabajas en 3+ días: aún no
  implementado; candidato natural es chequearlo dentro de /work.
- Contadores de caricias/golpes persistentes en /interact pat/punch (hoy son
  aleatorios solo para mostrar).
