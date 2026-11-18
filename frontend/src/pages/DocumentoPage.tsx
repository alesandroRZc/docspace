import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Anchor, Badge, Button, Container, Group, Loader, Stack, Textarea, Title } from "@mantine/core";
import { api } from "../api/cliente";
import { tieneNivel, type Documento } from "../api/tipos";

export default function DocumentoPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const [contenido, setContenido] = useState("");

  const { data: documento, isLoading, error } = useQuery({
    queryKey: ["documento", id],
    queryFn: () => api<Documento>(`/documents/${id}/`),
  });

  useEffect(() => {
    if (documento) {
      setContenido(documento.contenido_actual);
    }
  }, [documento]);

  const guardar = useMutation({
    mutationFn: () =>
      api(`/documents/${id}/save/`, {
        method: "POST",
        body: JSON.stringify({ contenido }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documento", id] });
      queryClient.invalidateQueries({ queryKey: ["versiones", id] });
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

  return (
    <Container py="xl">
      <Stack>
        <Anchor component={Link} to="/documentos">← Volver a mis documentos</Anchor>

        <Group justify="space-between">
          <Title order={2}>{documento.titulo}</Title>
          <Badge size="lg">{documento.mi_permiso}</Badge>
        </Group>

        <Textarea
          value={contenido}
          onChange={(evento) => setContenido(evento.currentTarget.value)}
          readOnly={!puedeEditar}
          autosize
          minRows={10}
        />

        {guardar.isSuccess && <Alert color="green">Versión guardada.</Alert>}
        {guardar.error && <Alert color="red">{guardar.error.message}</Alert>}

        {puedeEditar && (
          <Group justify="flex-end">
            <Button onClick={() => guardar.mutate()} loading={guardar.isPending}>
              Guardar nueva versión
            </Button>
          </Group>
        )}
      </Stack>
    </Container>
  );
}