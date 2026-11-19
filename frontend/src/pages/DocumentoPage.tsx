import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Anchor, Badge, Button, Container, Group, Loader, Stack, Textarea, Title, Text } from "@mantine/core";
import { api } from "../api/cliente";
import { tieneNivel, type Documento, type Usuario } from "../api/tipos";
import HistorialVersiones from "../components/HistorialVersiones";
import CompararVersiones from "../components/CompararVersiones";
import GestionAcceso from "../components/GestionAcceso";
import PresenciaDocumento from "../components/PresenciaDocumento";
import AvisoTurno, { AvisoConflicto } from "../components/AvisoTurno";
import { useDocumentoEnVivo, type MensajeServidor, type TurnoPublico } from "../api/tiempoReal";

// Cada cuánto se envía el texto en vivo mientras se escribe.
const ENVIO_MS = 300;
// Sin escribir durante este tiempo, el cliente guarda y libera el turno. El
// servidor igual lo libera solo a los 30 s; esto solo guarda antes.
const INACTIVIDAD_MS = 20_000;

type Conflicto = { versionActual: number; contenidoActual: string };
type Aviso = { color: string; texto: string };

export default function DocumentoPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const cargarDocumento = () => api<Documento>(`/documents/${id}/`);
  const { data: documento, isLoading, isFetching, error } = useQuery({
    queryKey: ["documento", id],
    queryFn: cargarDocumento,
  });
  const { data: yo } = useQuery({ queryKey: ["yo"], queryFn: () => api<Usuario>("/auth/me/") });

  // --- Estado del turno y del texto -------------------------------------
  const [turno, setTurno] = useState<TurnoPublico | null>(null);
  const [esMio, setEsMio] = useState(false);
  const [preparando, setPreparando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [miTexto, setMiTexto] = useState("");
  // Texto en vivo de quien edita (o el mío recién guardado, hasta que llegue la versión).
  const [vivo, setVivo] = useState<string | null>(null);
  const [versionEsperada, setVersionEsperada] = useState<number | null>(null);
  const [rechazadoPorTamano, setRechazadoPorTamano] = useState(false);

  // --- Avisos -------------------------------------------------------------
  const [conflicto, setConflicto] = useState<Conflicto | null>(null);
  const [avisoVersion, setAvisoVersion] = useState<number | null>(null);
  const [textoNoGuardado, setTextoNoGuardado] = useState<string | null>(null);
  const [aviso, setAviso] = useState<Aviso | null>(null);

  // Refs: los mensajes del servidor llegan entre renders y necesitan el valor
  // más reciente, no el del último render.
  const esMioRef = useRef(false);
  const pidiendoRef = useRef(false);
  const guardandoRef = useRef(false);
  const esperandoMiVersionRef = useRef(false);
  const miTextoRef = useRef("");
  const ultimoEnviadoRef = useRef("");
  const envioRef = useRef<number | undefined>(undefined);
  const inactividadRef = useRef<number | undefined>(undefined);

  function invalidar() {
    queryClient.invalidateQueries({ queryKey: ["documento", id] });
    queryClient.invalidateQueries({ queryKey: ["versiones", id] });
  }

  function cancelarTemporizadores() {
    window.clearTimeout(envioRef.current);
    window.clearTimeout(inactividadRef.current);
    envioRef.current = undefined;
    inactividadRef.current = undefined;
  }

  function fijarGuardando(valor: boolean) {
    guardandoRef.current = valor;
    setGuardando(valor);
  }

  function perderTurno() {
    cancelarTemporizadores();
    // Nunca perder datos en silencio: si quedó texto sin llegar al servidor, mostrarlo.
    if (esMioRef.current && miTextoRef.current !== ultimoEnviadoRef.current) {
      setTextoNoGuardado(miTextoRef.current);
    }
    esMioRef.current = false;
    setEsMio(false);
    setPreparando(false);
    setConflicto(null);
    fijarGuardando(false);
  }

  async function empezarAEditar() {
    esMioRef.current = true;
    setEsMio(true);
    setPreparando(true);
    setConflicto(null);
    setAvisoVersion(null);
    setTextoNoGuardado(null);
    try {
      // Siempre desde el contenido más reciente: nunca editar sobre una versión
      // más vieja que la base del turno (si alguien guarda justo ahora, el
      // conflicto saltará al guardar en vez de sobrescribir en silencio).
      const fresco = await queryClient.fetchQuery({ queryKey: ["documento", id], queryFn: cargarDocumento, staleTime: 0 });
      if (!esMioRef.current) return;
      miTextoRef.current = fresco.contenido_actual;
      ultimoEnviadoRef.current = fresco.contenido_actual;
      setMiTexto(fresco.contenido_actual);
      programarInactividad();
    } catch {
      setAviso({ color: "red", texto: "No se pudo cargar el documento para editar. Inténtalo de nuevo." });
      enVivo.enviar({ tipo: "liberar_turno" });
    } finally {
      setPreparando(false);
    }
  }

  function alRecibir(mensaje: MensajeServidor) {
    switch (mensaje.tipo) {
      case "conectado":
        // Tras una (re)conexión pudo haber cambios que no vimos.
        invalidar();
        break;

      case "turno": {
        const nuevo = mensaje.turno;
        setTurno(nuevo);
        const esDeMiUsuario = nuevo !== null && yo !== undefined && nuevo.usuario_id === yo.id;

        if (esDeMiUsuario && pidiendoRef.current) {
          pidiendoRef.current = false;
          if (!esMioRef.current) void empezarAEditar();
          break;
        }
        if (esDeMiUsuario && esMioRef.current) break; // sigue siendo mío

        pidiendoRef.current = false;
        if (esMioRef.current) {
          // Terminó mi turno: mostrar mi texto hasta que llegue la versión guardada.
          if (guardandoRef.current) esperandoMiVersionRef.current = true;
          setVivo(miTextoRef.current);
          perderTurno();
        } else if (nuevo !== null) {
          setVivo(null); // empieza a editar otra persona: su texto llega con "cambio"
        }
        break;
      }

      case "turno_ocupado":
        pidiendoRef.current = false;
        setAviso({ color: "yellow", texto: `${mensaje.turno?.nombre ?? "Otra persona"} está editando. Espera a que termine.` });
        break;

      case "cambio":
        if (!esMioRef.current) setVivo(mensaje.contenido);
        break;

      case "version_guardada":
        invalidar(); // historial y contenido, sin recargar la página
        if (esMioRef.current) {
          // Estoy editando: NO reemplazar mi texto. El conflicto se resuelve al guardar.
          setAvisoVersion(mensaje.numero_version);
        } else {
          setVersionEsperada(mensaje.numero_version);
          if (esperandoMiVersionRef.current) {
            esperandoMiVersionRef.current = false;
            setAviso({ color: "green", texto: `Versión ${mensaje.numero_version} guardada.` });
          }
        }
        break;

      case "conflicto":
        fijarGuardando(false);
        setAvisoVersion(null);
        setConflicto({ versionActual: mensaje.version_actual, contenidoActual: mensaje.contenido_actual });
        break;

      case "borrador_en_conflicto":
        invalidar();
        setAviso({
          color: "orange",
          texto: `El texto de ${mensaje.autor} chocó con la versión ${mensaje.version_actual} y no se aplicó; quedó guardado en la bitácora.`,
        });
        break;

      case "error":
        fijarGuardando(false);
        if (mensaje.motivo === "turno_vencido" || mensaje.motivo === "sin_turno") {
          // Lo último que envié fue rechazado: no llegó al servidor.
          if (esMioRef.current || mensaje.motivo === "turno_vencido") setTextoNoGuardado(miTextoRef.current);
          perderTurno();
          setAviso({ color: "yellow", texto: "Perdiste el turno de edición." });
        } else if (mensaje.codigo === 413) {
          setRechazadoPorTamano(true);
          setAviso({ color: "red", texto: "Tu texto supera el tamaño máximo permitido. Los últimos cambios no se enviaron: reduce el texto para poder guardarlo." });
        } else {
          setAviso({ color: "red", texto: mensaje.detalle });
        }
        break;
    }
  }

  const enVivo = useDocumentoEnVivo(id, alRecibir);

  // --- Acciones del editor -------------------------------------------------

  function enviarPendiente() {
    window.clearTimeout(envioRef.current);
    envioRef.current = undefined;
    if (!esMioRef.current || miTextoRef.current === ultimoEnviadoRef.current) return;
    if (enVivo.enviar({ tipo: "editar", contenido: miTextoRef.current })) {
      ultimoEnviadoRef.current = miTextoRef.current;
    }
  }

  function programarInactividad() {
    window.clearTimeout(inactividadRef.current);
    inactividadRef.current = window.setTimeout(() => guardar(), INACTIVIDAD_MS);
  }

  function alEscribir(texto: string) {
    miTextoRef.current = texto;
    setMiTexto(texto);
    setRechazadoPorTamano(false);
    window.clearTimeout(envioRef.current);
    envioRef.current = window.setTimeout(enviarPendiente, ENVIO_MS);
    programarInactividad();
  }

  function pedirTurno() {
    pidiendoRef.current = true;
    setAviso(null);
    enVivo.enviar({ tipo: "pedir_turno" });
  }

  function guardar(versionBase?: number) {
    enviarPendiente(); // lo último escrito sale antes de liberar
    cancelarTemporizadores();
    setConflicto(null);
    fijarGuardando(true);
    enVivo.enviar(
      versionBase === undefined
        ? { tipo: "liberar_turno" }
        : { tipo: "liberar_turno", version_base: versionBase },
    );
  }

  function descartar() {
    cancelarTemporizadores();
    setConflicto(null);
    miTextoRef.current = ultimoEnviadoRef.current; // descartado a propósito: no avisar de "texto no guardado"
    enVivo.enviar({ tipo: "liberar_turno", descartar: true });
  }

  function seguirEditando() {
    setConflicto(null);
    programarInactividad();
  }

  // Antes de cerrar la pestaña o salir de la página: enviar lo pendiente.
  // (Al cerrar la conexión, el servidor guarda el borrador como versión.)
  const enviar = enVivo.enviar;
  useEffect(() => {
    const vaciar = () => {
      if (esMioRef.current && miTextoRef.current !== ultimoEnviadoRef.current) {
        enviar({ tipo: "editar", contenido: miTextoRef.current });
      }
    };
    window.addEventListener("beforeunload", vaciar);
    return () => {
      window.removeEventListener("beforeunload", vaciar);
      vaciar();
      window.clearTimeout(envioRef.current);
      window.clearTimeout(inactividadRef.current);
    };
  }, [enviar]);

  const eliminar = useMutation({
    mutationFn: () => api(`/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      navigate("/documentos");
    },
  });

  if (isLoading) return <Container py="xl"><Loader /></Container>;
  if (error || !documento) {
    return (
      <Container py="xl">
        <Alert color="red">Documento no encontrado.</Alert>
        <Anchor component={Link} to="/documentos">← Volver</Anchor>
      </Container>
    );
  }

  const puedeEditar = tieneNivel(documento.mi_permiso, "EDICION");
  const puedeAdministrar = tieneNivel(documento.mi_permiso, "ADMINISTRACION");
  const conectado = enVivo.conexion === "conectado";
  const editable = esMio && conectado && !preparando && !guardando;

  // Qué texto se ve:
  // - si edito yo: mi texto (nunca lo pisa una versión que llegue);
  // - si edita otra persona: su texto en vivo;
  // - si nadie edita: la última versión, o el texto recién guardado mientras
  //   la consulta todavía trae la versión nueva (evita un parpadeo).
  const esperandoVersionNueva = versionEsperada !== null && documento.version_actual < versionEsperada;
  const textoMostrado = esMio
    ? miTexto
    : turno !== null
      ? (vivo ?? documento.contenido_actual)
      : (vivo !== null && esperandoVersionNueva ? vivo : documento.contenido_actual);

  return (
    <Container py="xl">
      <Stack>
        <Anchor component={Link} to="/documentos">← Volver a mis documentos</Anchor>

        <Group justify="space-between">
          <Title order={2}>{documento.titulo}</Title>
          <Badge size="lg">{documento.mi_permiso}</Badge>
        </Group>
        <Text size="sm" c="dimmed">Creado por {documento.creador_nombre}</Text>
        <PresenciaDocumento conexion={enVivo.conexion} presentes={enVivo.presentes} />

        <AvisoTurno turno={turno} esMio={esMio} />

        {aviso && (
          <Alert color={aviso.color} withCloseButton onClose={() => setAviso(null)}>{aviso.texto}</Alert>
        )}
        {avisoVersion !== null && (
          <Alert color="orange" withCloseButton onClose={() => setAvisoVersion(null)}>
            Alguien guardó la versión {avisoVersion}. Tu texto no se reemplazó; al guardar se comprobará si hay conflicto.
          </Alert>
        )}
        {textoNoGuardado !== null && (
          <Alert color="red" title="Lo último que escribiste no se guardó" withCloseButton onClose={() => setTextoNoGuardado(null)}>
            <Stack>
              <Text size="sm">Cópialo antes de seguir para no perderlo.</Text>
              <Textarea value={textoNoGuardado} readOnly autosize minRows={3} maxRows={10} />
            </Stack>
          </Alert>
        )}
        {esMio && conflicto && (
          <AvisoConflicto
            miTexto={miTexto}
            versionActual={conflicto.versionActual}
            contenidoActual={conflicto.contenidoActual}
            onGuardarEncima={() => guardar(conflicto.versionActual)}
            onDescartar={descartar}
            onSeguirEditando={seguirEditando}
          />
        )}

        <Textarea
          value={textoMostrado}
          onChange={(evento) => alEscribir(evento.currentTarget.value)}
          onBlur={enviarPendiente}
          readOnly={!editable}
          autosize
          minRows={10}
        />

        <Group justify="flex-end">
          {puedeAdministrar && (
            <Button
              color="red"
              variant="light"
              loading={eliminar.isPending}
              onClick={() => {
                if (window.confirm("¿Eliminar este documento? Su historial se conservará.")) {
                  eliminar.mutate();
                }
              }}
            >
              Eliminar documento
            </Button>
          )}
          {puedeEditar && !esMio && (
            <Button onClick={pedirTurno} disabled={!conectado || turno !== null || isFetching || !yo}>
              {turno !== null ? `Editando: ${turno.nombre}` : "Editar"}
            </Button>
          )}
          {esMio && (
            <Button onClick={() => guardar()} loading={guardando || preparando} disabled={rechazadoPorTamano || !conectado}>
              Guardar
            </Button>
          )}
        </Group>

        <HistorialVersiones documentoId={documento.id} miPermiso={documento.mi_permiso} />
        <CompararVersiones documentoId={documento.id} />
        {puedeAdministrar && <GestionAcceso documento={documento} />}
      </Stack>
    </Container>
  );
}
