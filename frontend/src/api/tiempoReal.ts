import { useCallback, useEffect, useRef, useState } from "react";
import { obtenerToken } from "./cliente";
import type { Nivel } from "./tipos";

// Mismo valor por defecto que cliente.ts. El WebSocket vive en el mismo
// servidor que la API, sin el sufijo /api: http://host:8000/api -> ws://host:8000
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
const WS_URL = API_URL.replace(/^http/, "ws").replace(/\/api\/?$/, "");

const LATIDO_MS = 10_000;
const ESPERA_MAXIMA_MS = 10_000;

// Códigos de cierre del servidor (documents/consumers.py).
const CIERRE_NO_AUTENTICADO = 4401;
const CIERRE_NO_ENCONTRADO = 4404;

export type UsuarioPresente = { id: string; nombre: string };
export type TurnoPublico = { usuario_id: string; nombre: string };

export type MensajeServidor =
  | { tipo: "conectado"; nivel: Nivel }
  | { tipo: "presencia"; usuarios: UsuarioPresente[] }
  | { tipo: "turno"; turno: TurnoPublico | null }
  | { tipo: "turno_ocupado"; turno: TurnoPublico | null }
  | { tipo: "cambio"; contenido: string; usuario_id: string; nombre: string }
  | { tipo: "version_guardada"; numero_version: number; autor: string }
  | { tipo: "conflicto"; version_actual: number; contenido_actual: string }
  | { tipo: "borrador_en_conflicto"; autor: string; version_actual: number }
  | { tipo: "error"; codigo: number; motivo: string; detalle: string };

export type MensajeCliente =
  | { tipo: "latido" }
  | { tipo: "pedir_turno" }
  | { tipo: "editar"; contenido: string }
  | { tipo: "liberar_turno"; version_base?: number; descartar?: boolean };

export type EstadoConexion =
  | "conectando"
  | "conectado"
  | "reconectando"
  | "sin_acceso"       // 4404: el documento ya no existe o perdiste el acceso
  | "sesion_expirada"; // 4401: token ausente o vencido

type Estado = {
  documentoId: string;
  conexion: EstadoConexion;
  nivel: Nivel | null;
  presentes: UsuarioPresente[];
};

function estadoInicial(documentoId: string): Estado {
  return { documentoId, conexion: "conectando", nivel: null, presentes: [] };
}

/**
 * Conexión en tiempo real con un documento.
 *
 * - Autentica con el JWT como subprotocolo (no va en la URL).
 * - Envía un latido cada 10 s (mantiene solo la presencia).
 * - Reconecta con espera exponencial (1 s, 2 s, 4 s... hasta 10 s), salvo si
 *   el servidor cerró por sesión (4401) o por acceso (4404).
 * - `alRecibir` recibe todos los mensajes del servidor (lo usa el editor).
 *
 * Los permisos los decide el servidor; este hook solo refleja lo que recibe.
 */
export function useDocumentoEnVivo(
  documentoId: string | undefined,
  alRecibir?: (mensaje: MensajeServidor) => void,
) {
  const [estado, setEstado] = useState<Estado | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const alRecibirRef = useRef(alRecibir);

  useEffect(() => {
    alRecibirRef.current = alRecibir;
  });

  useEffect(() => {
    if (!documentoId) return;

    let cancelado = false;
    let intentos = 0;
    let reintento: number | undefined;
    let latido: number | undefined;

    // El estado lleva el id del documento: si cambia de documento, el estado
    // anterior se ignora sin tener que reiniciarlo dentro del efecto.
    const actualizar = (cambio: Partial<Estado>) =>
      setEstado((previo) => ({
        ...(previo?.documentoId === documentoId ? previo : estadoInicial(documentoId)),
        ...cambio,
      }));

    function conectar() {
      const token = obtenerToken();
      const ws = new WebSocket(
        `${WS_URL}/ws/documents/${documentoId}/`,
        token ? ["access_token", token] : [],
      );
      socketRef.current = ws;

      ws.onopen = () => {
        intentos = 0;
        latido = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ tipo: "latido" }));
        }, LATIDO_MS);
      };

      ws.onmessage = (evento) => {
        const mensaje = JSON.parse(evento.data) as MensajeServidor;
        if (mensaje.tipo === "conectado") actualizar({ conexion: "conectado", nivel: mensaje.nivel });
        if (mensaje.tipo === "presencia") actualizar({ presentes: mensaje.usuarios });
        alRecibirRef.current?.(mensaje);
      };

      ws.onclose = (evento) => {
        window.clearInterval(latido);
        if (socketRef.current === ws) socketRef.current = null;
        if (cancelado) return;

        if (evento.code === CIERRE_NO_AUTENTICADO) return actualizar({ conexion: "sesion_expirada", presentes: [] });
        if (evento.code === CIERRE_NO_ENCONTRADO) return actualizar({ conexion: "sin_acceso", presentes: [] });

        actualizar({ conexion: "reconectando", presentes: [] });
        const espera = Math.min(1000 * 2 ** intentos, ESPERA_MAXIMA_MS);
        intentos += 1;
        reintento = window.setTimeout(conectar, espera);
      };
    }

    conectar();

    return () => {
      cancelado = true;
      window.clearTimeout(reintento);
      window.clearInterval(latido);
      socketRef.current?.close(1000);
      socketRef.current = null;
    };
  }, [documentoId]);

  const enviar = useCallback((mensaje: MensajeCliente) => {
    const ws = socketRef.current;
    if (ws?.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(mensaje));
    return true;
  }, []);

  const actual = documentoId && estado?.documentoId === documentoId ? estado : null;
  return {
    conexion: actual?.conexion ?? "conectando",
    nivel: actual?.nivel ?? null,
    presentes: actual?.presentes ?? [],
    enviar,
  };
}
