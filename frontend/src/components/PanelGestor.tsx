import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Group, Select, Stack, TextInput, Title } from "@mantine/core";
import { api } from "../api/cliente";
import type { Espacio, Usuario } from "../api/tipos";

export default function PanelGestor({ yo }: { yo: Usuario }) {
  const queryClient = useQueryClient();
  const [nombreEspacio, setNombreEspacio] = useState("");
  const [espacioId, setEspacioId] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");

  const { data: espacios } = useQuery({
    queryKey: ["espacios"],
    queryFn: () => api<Espacio[]>("/workspaces/"),
  });

  const misEspacios = (espacios ?? []).filter((espacio) => espacio.gestor === yo.id);

  const crearEspacio = useMutation({
    mutationFn: () =>
      api<Espacio>("/workspaces/", {
        method: "POST",
        body: JSON.stringify({ nombre: nombreEspacio }),
      }),
    onSuccess: (nuevo) => {
      setNombreEspacio("");
      setEspacioId(nuevo.id);
      queryClient.invalidateQueries({ queryKey: ["espacios"] });
    },
  });

  const crearDocumento = useMutation({
    mutationFn: () =>
      api("/documents/", {
        method: "POST",
        body: JSON.stringify({ espacio: espacioId, titulo }),
      }),
    onSuccess: () => {
      setTitulo("");
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
    },
  });

  return (
    <Card withBorder mb="lg">
      <Stack>
        <Title order={4}>Panel del Gestor</Title>

        <Group align="flex-end">
          <TextInput
            label="Nuevo espacio de trabajo"
            placeholder="Ej. Área de ventas"
            value={nombreEspacio}
            onChange={(e) => setNombreEspacio(e.currentTarget.value)}
            style={{ flex: 1, minWidth: 200 }}
                      />
          <Button onClick={() => crearEspacio.mutate()} loading={crearEspacio.isPending} disabled={!nombreEspacio}>
            Crear espacio
          </Button>
        </Group>
        {crearEspacio.error && <Alert color="red">{crearEspacio.error.message}</Alert>}

        <Group align="flex-end">
          <Select
            label="Espacio"
            placeholder="Elige un espacio"
            data={misEspacios.map((espacio) => ({ value: espacio.id, label: espacio.nombre }))}
            value={espacioId}
            onChange={setEspacioId}
            style={{ flex: 1, minWidth: 200 }}
          />
          <TextInput
            label="Nuevo documento"
            placeholder="Título del documento"
            value={titulo}
            onChange={(e) => setTitulo(e.currentTarget.value)}
            style={{ flex: 2, minWidth: 200 }}          />
          <Button
            onClick={() => crearDocumento.mutate()}
            loading={crearDocumento.isPending}
            disabled={!espacioId || !titulo}
          >
            Crear documento
          </Button>
        </Group>
        {crearDocumento.error && <Alert color="red">{crearDocumento.error.message}</Alert>}
      </Stack>
    </Card>
  );
}