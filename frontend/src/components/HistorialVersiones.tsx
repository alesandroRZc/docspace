import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Badge, Button, Card, Group, Loader, Stack, Text, Title } from "@mantine/core";
import { api } from "../api/cliente";
import { tieneNivel, type Nivel, type Version } from "../api/tipos";

type Props = {
  documentoId: string;
  miPermiso: Nivel | null;
};

export default function HistorialVersiones({ documentoId, miPermiso }: Props) {
  const queryClient = useQueryClient();
  const puedeRestaurar = tieneNivel(miPermiso, "ADMINISTRACION");

  const { data: versiones, isLoading } = useQuery({
    queryKey: ["versiones", documentoId],
    queryFn: () => api<Version[]>(`/documents/${documentoId}/versions/`),
  });

  const restaurar = useMutation({
    mutationFn: (numero: number) =>
      api(`/documents/${documentoId}/versions/${numero}/restore/`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documento", documentoId] });
      queryClient.invalidateQueries({ queryKey: ["versiones", documentoId] });
    },
  });

  if (isLoading) return <Loader />;

  return (
    <Stack>
      <Title order={3}>Historial de versiones</Title>
      {restaurar.error && <Alert color="red">{restaurar.error.message}</Alert>}

      {versiones?.map((version) => (
        <Card key={version.id} withBorder>
          <Group justify="space-between">
            <Group>
              <Badge variant="light">v{version.numero_version}</Badge>
              <Text size="sm">{new Date(version.fecha_creacion).toLocaleString()}</Text>
              {version.restaurada_desde && <Badge color="grape">Restaurada</Badge>}
            </Group>

            {puedeRestaurar && (
              <Button
                size="xs"
                variant="light"
                onClick={() => restaurar.mutate(version.numero_version)}
                loading={restaurar.isPending}
              >
                Restaurar
              </Button>
            )}
          </Group>
        </Card>
      ))}
    </Stack>
  );
}