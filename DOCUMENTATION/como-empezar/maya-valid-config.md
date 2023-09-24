---
layout: page
menubar: docs_menu
title: Configuración Maya | Core
subtitle: Cómo empezar
show_sidebar: false
hero_height: is-fullwidth
---

despues de moodle-config!!

## Configuración Maya | Valid

> A lo largo del documento, el prompt **$** indica un comando a introducir en el host, mientras que el prompt **>** indica un comando a introducir en el contenedor. Además, **[PWD_MODULO]** indica el directorio raíz del módulo.

1. [ ] Configurar la ruta de almacenamiento de las convalidaciones
  
      Como _administrador_ acceder en _Odoo_:

         Ajustes / Maya | Valid / Convalidaciones / Carpeta

      Una configuración habitual puede ser _/mnt/odoo-repo/convalidaciones_

### Creación de las tareas

2. [ ] Utilizando de plantilla el fichero _[PWD_MODULO]/misc/scripts/data_task_valid/tasks_test.csv_ añadir todas las tareas _Moodle_ que dan soporte a las convalidaciones, para posteriormente incorporarlas a **Maya** mediante el script _[PWD_MODULO]../maya_core/misc/scripts/create_tasks/create_tasks.py_

    ```
    cd [PWD_MODULO]../maya_core/misc/scripts/create_tasks/
    chmod +x create_tasks.py
    ./create_tasks.py -sr USERADMIN -ps PASSADMIN -db NOMDB ../../../../maya_valid/misc/scripts/data_task_valid/FICHERO.csv 
    ```
    donde: 

      * USERADMIN: usuario administrador.
      * PASSADMIN: pasword del usuario administrador.
      * NOMDB: es el nombre de la base de datos. 
      * FICHERO.csv: fichero con los datos de las tareas.

    En el caso de estar trabajando con [odoodock](https://aoltra.github.io/odoodock/) hay que ejecutar el script desde dentro del contenedor:

    ```
    $ docker exec -it odoodock-web-1 bash
    > cd /mnt/extra-addons/maya_core/misc/scripts/create_tasks
    > chmod +x create_tasks.py
    > ./create_tasks.py -sr USERADMIN -ps PASSADMIN -db NOMDB ../../../../maya_valid/misc/scripts/data_task_valid/FICHERO.csv 
    ```

    > Es muy importante que el código del aula siga las indicaciones comentadas en el apartado 2 del documento de [configuración de Moodle](/maya-core/docs/requirements/moodle-config).

### Asignación de roles

3. [ ] Desde Maya | Core / Curso / Empleados, se asignan los convalidadores de cada ciclo. 

Además, en caso de que no lo estuvieran, se asignan a las personas del equipo de coordinación de ciclos (jefe de estudios, coordinador...) que serán los encargados de validar y a las personas del equipo de secretaria que pasarán los datos al expediente del alumno.

## odoo.conf

4. [ ] En caso de utilizar _pdftk_ como un ejecutable interno, es necesario aumentar el valor de la variable _limit_memory_hard_

```
limit_memory_hard = 8684354560
```

> Es necesario reiniciar Odoo para que los cambios tengan efecto