import { Alert, Button, Group, SimpleGrid, Stack, Text, Textarea } from "@mantine/core";
import type { TurnoPublico } from "../api/tiempoReal";

type Props = {
  turno: TurnoPublico | null;
  esMio: boolean;
};

/** Quién tiene el turno de edición. */
export default function AvisoTurno({ turno, esMio }: Props) {
  if (esMio) {
    return (
      <Alert color="blue" variant="light">
        Estás editando. Los demás ven tus cambios en vivo. Se guarda una versión al pulsar
        «Guardar» o tras 20 segundos sin escribir.
      </Alert>
    );
  }
  if (turno) {
    return (
      <Alert color="yellow" variant="light">
        Editando: <b>{turno.nombre}</b>. Verás sus cambios en vivo.
      </Alert>
    );
  }
  return null;
}

type ConflictoProps = {
  miTexto: string;
  versionActual: number;
  contenidoActual: string;
  onGuardarEncima: () => void;
  onDescartar: () => void;
  onSeguirEditando: () => void;
};

/**
 * Otra persona guardó mientras editabas. Nada se guarda ni se pierde hasta que
 * elijas: tu texto sigue en el editor y en el servidor (borrador).
 */
export function AvisoConflicto({
  miTexto,
  versionActual,
  contenidoActual,
  onGuardarEncima,
  onDescartar,
  onSeguirEditando,
}: ConflictoProps) {
  return (
    <Alert color="orange" title={`Conflicto: alguien guardó la versión ${versionActual} mientras editabas`}>
      <Stack>
        <Text size="sm">
          Tu texto no se guardó todavía. Compáralo con la versión actual y decide.
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Textarea label="Tu texto" value={miTexto} readOnly autosize minRows={4} maxRows={12} />
          <Textarea label={`Versión ${versionActual} (actual)`} value={contenidoActual} readOnly autosize minRows={4} maxRows={12} />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button variant="default" onClick={onSeguirEditando}>Seguir editando</Button>
          <Button color="red" variant="light" onClick={onDescartar}>Descartar mi texto</Button>
          <Button color="orange" onClick={onGuardarEncima}>
            Guardar mi texto encima de la versión {versionActual}
          </Button>
        </Group>
      </Stack>
    </Alert>
  );
}
