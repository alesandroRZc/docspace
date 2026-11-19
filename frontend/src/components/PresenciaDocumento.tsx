import { Alert, Avatar, Badge, Group, Text, Tooltip } from "@mantine/core";
import type { EstadoConexion, UsuarioPresente } from "../api/tiempoReal";

type Props = {
  conexion: EstadoConexion;
  presentes: UsuarioPresente[];
};

const INDICADOR: Record<EstadoConexion, { color: string; texto: string }> = {
  conectando: { color: "gray", texto: "Conectando…" },
  conectado: { color: "green", texto: "En vivo" },
  reconectando: { color: "yellow", texto: "Reconectando…" },
  sin_acceso: { color: "red", texto: "Sin acceso" },
  sesion_expirada: { color: "red", texto: "Sesión expirada" },
};

export default function PresenciaDocumento({ conexion, presentes }: Props) {
  const indicador = INDICADOR[conexion];

  return (
    <>
      <Group gap="sm">
        <Badge color={indicador.color} variant="dot">{indicador.texto}</Badge>

        {presentes.length > 0 && (
          <>
            <Tooltip.Group openDelay={200} closeDelay={100}>
              <Avatar.Group spacing="sm">
                {presentes.map((usuario) => (
                  <Tooltip key={usuario.id} label={usuario.nombre} withArrow>
                    <Avatar name={usuario.nombre} color="initials" radius="xl" size="sm" />
                  </Tooltip>
                ))}
              </Avatar.Group>
            </Tooltip.Group>
            <Text size="sm" c="dimmed">
              {presentes.length === 1 ? "1 persona en el documento" : `${presentes.length} personas en el documento`}
            </Text>
          </>
        )}
      </Group>

      {conexion === "sin_acceso" && (
        <Alert color="red">Ya no tienes acceso a este documento o fue eliminado.</Alert>
      )}
      {conexion === "sesion_expirada" && (
        <Alert color="red">Tu sesión expiró. Vuelve a iniciar sesión para seguir en vivo.</Alert>
      )}
    </>
  );
}
