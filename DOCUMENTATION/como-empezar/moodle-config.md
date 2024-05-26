## Configuración Moodle 

Para el correcto funcionamento de **Maya | Valid** con Moodle, es necesario:

1. [ ] Generar, por cada ciclo formativo, el fichero _mbz_ que incluye la sección con las diferentes tareas. Para ello desde _Odoo_ acceder a _Centro/Ciclos_ y acceder al ciclo correspondiente. Desde él, pulsar el botón _Genera mbz tareas convalidaciones_. El botón descarga de manera automatica un fichero denominado *validation_section_XXX_YYYY.mbz*, donde XXX la abreviatura del ciclo y YYYYY el código.

2. [ ] En cada una de las aulas de tutoría en las que queremos realizar el proceso de convalidaciones:

    > Dichas aulas tienen que esta creadas en Maya. Ver [Creación de las aulas virtuales](https://CEED-informatica.github.io/maya-core/docs/maya/connect-maya-moodle#creacion-de-las-aulas-virtuales)

    - añadir una sección
    - moverla hasta la primera posición
    - restaurar el fichero _.mbz_ descargado en el paso 1. 

      > IMPORTANTE: La restauración tiene que hacerse de manera combinada al aula.

3. [ ] Eliminar la sección de convalidaciones del curso anterior.

