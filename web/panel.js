/* Panel del bot: JavaScript vanilla, sin frameworks ni CDNs. */

(function () {
    "use strict";

    var CAMPOS = [
        "work_mode",
        "minigame",
        "turns_per_session",
        "sessions_per_day",
        "health_loss_chance",
        "lucky_chance",
        "welcome_channel_id",
        "ticket_category_id",
        "alliance_channel_id",
        "hunter_role_id",
        "alliance_role_id"
    ];

    function leerCuerpo() {
        var cuerpo = {};
        CAMPOS.forEach(function (nombre) {
            var el = document.querySelector('[name="' + nombre + '"]');
            if (el) {
                cuerpo[nombre] = String(el.value).trim();
            }
        });
        return cuerpo;
    }

    function mostrarMensaje(texto, clase) {
        var mensaje = document.querySelector("#mensaje");
        if (!mensaje) return;
        mensaje.textContent = texto;
        mensaje.className = "mensaje visible " + clase;
    }

    function limpiarErrores() {
        document.querySelectorAll(".error-campo").forEach(function (el) {
            el.className = "error-campo";
            el.textContent = "";
        });
    }

    function marcarErrores(texto) {
        // Muestra el mensaje del servidor junto a cada campo por si acaso
        if (!texto) return;
        CAMPOS.forEach(function (nombre) {
            var el = document.querySelector("#err-" + nombre);
            if (el && texto.indexOf(nombre) !== -1) {
                el.textContent = texto;
                el.className = "error-campo visible";
            }
        });
    }

    function refrescarAuditoria(registros) {
        var cuerpo = document.querySelector("#tabla-auditoria tbody");
        if (!cuerpo || !registros) return;
        cuerpo.innerHTML = "";
        registros.slice().reverse().forEach(function (registro) {
            var fila = document.createElement("tr");
            [registro.campo, registro.valor_anterior, registro.valor_nuevo,
             registro.actor_name, registro.fecha].forEach(function (valor) {
                var celda = document.createElement("td");
                celda.textContent = valor;
                fila.appendChild(celda);
            });
            cuerpo.appendChild(fila);
        });
    }

    function guardar() {
        var boton = document.querySelector("#boton-guardar");
        var coincidencia = window.location.pathname.match(/^\/panel\/servidor\/(\d+)$/);
        if (!coincidencia) return;
        var url = "/panel/api/servidor/" + coincidencia[1] + "/config";

        limpiarErrores();
        if (boton) boton.disabled = true;

        fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify(leerCuerpo())
        })
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    return { estado: respuesta.status, datos: datos };
                });
            })
            .then(function (resultado) {
                if (resultado.datos && resultado.datos.ok) {
                    var cantidad = resultado.datos.cambios ? resultado.datos.cambios.length : 0;
                    mostrarMensaje("Cambios guardados (" + cantidad + " campo/s).", "ok");
                    refrescarAuditoria(resultado.datos.auditoria);
                } else {
                    var error = resultado.datos && resultado.datos.error
                        ? resultado.datos.error
                        : "No se pudo guardar.";
                    mostrarMensaje(error, "error");
                    marcarErrores(error);
                }
            })
            .catch(function () {
                mostrarMensaje("Error de red al guardar.", "error");
            })
            .then(function () {
                if (boton) boton.disabled = false;
            });
    }

    // Exponer para el onclick del boton
    window.guardar = guardar;
})();
