import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Divider, Group, PasswordInput, Select, SimpleGrid, Stack, TextInput, Title } from "@mantine/core";
import { api } from "../api/cliente";
import type { Documento, Espacio, Nivel, Usuario } from "../api/tipos";

export default function GestionAcceso({ documento }: { documento: Documento }) {
  const [emailMiembro, setEmailMiembro] = useState("");
  const [nuevo, setNuevo] = useState({ nombre: "", username: "", email: "", password: "" });
  const [emailPermiso, setEmailPermiso] = useState("");
  const [nivel, setNivel] = useState<string | null>("LECTURA");

  const { data: yo } = useQuery({ queryKey: ["yo"], queryFn: () => api<Usuario>("/auth/me/") });
  const { data: espacios } = useQuery({ queryKey: ["espacios"], queryFn: () => api<Espacio[]>("/workspaces/") });

  const espacio = espacios?.find((e) => e.id === documento.espacio);
  const esGestor = Boolean(yo && espacio && espacio.gestor === yo.id);

  const agregarMiembro = useMutation({
    mutationFn: () =>
      api(`/workspaces/${documento.espacio}/members/`, {
        method: "POST",
        body: JSON.stringify({ email: emailMiembro }),
      }),
    onSuccess: () => setEmailMiembro(""),
  });

  const crearColaborador = useMutation({
    mutationFn: () =>
      api(`/workspaces/${documento.espacio}/members/create/`, {
        method: "POST",
        body: JSON.stringify(nuevo),
      }),
    onSuccess: () => setNuevo({ nombre: "", username: "", email: "", password: "" }),
  });

  const asignarPermiso = useMutation({
    mutationFn: () =>
      api(`/documents/${documento.id}/permissions/`, {
        method: "POST",
        body: JSON.stringify({ email: emailPermiso, nivel: nivel as Nivel }),
      }),
    onSuccess: () => setEmailPermiso(""),
  });

   return (
    <Card withBorder>
      <Stack>
        <Title order={3}>Gestión de acceso</Title>

        {esGestor && (
          <>
            <Title order={5}>Agregar miembro al espacio</Title>
            <Group align="flex-end">
              <TextInput
                label="Correo del usuario"
                value={emailMiembro}
                onChange={(e) => setEmailMiembro(e.currentTarget.value)}
                style={{ flex: 1, minWidth: 200 }}
              />
              <Button onClick={() => agregarMiembro.mutate()} loading={agregarMiembro.isPending} disabled={!emailMiembro}>
                Agregar
              </Button>
            </Group>
            {agregarMiembro.isSuccess && <Alert color="green">Miembro agregado.</Alert>}
            {agregarMiembro.error && <Alert color="red">{agregarMiembro.error.message}</Alert>}

            <Divider />

            <Title order={5}>Crear colaborador</Title>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <TextInput label="Nombre" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.currentTarget.value })} />
              <TextInput label="Usuario" value={nuevo.username} onChange={(e) => setNuevo({ ...nuevo, username: e.currentTarget.value })} />
              <TextInput label="Correo" value={nuevo.email} onChange={(e) => setNuevo({ ...nuevo, email: e.currentTarget.value })} />
              <PasswordInput
                label="Contraseña"
                autoComplete="new-password"
                value={nuevo.password}
                onChange={(e) => setNuevo({ ...nuevo, password: e.currentTarget.value })}
              />
            </SimpleGrid>
            <Group justify="flex-end">
              <Button onClick={() => crearColaborador.mutate()} loading={crearColaborador.isPending}>
                Crear colaborador
              </Button>
            </Group>
            {crearColaborador.isSuccess && <Alert color="green">Colaborador creado y agregado al espacio.</Alert>}
            {crearColaborador.error && <Alert color="red">{crearColaborador.error.message}</Alert>}

            <Divider />
          </>
        )}

        <Title order={5}>Asignar permiso sobre este documento</Title>
        <Group align="flex-end">
          <TextInput
            label="Correo del miembro"
            value={emailPermiso}
            onChange={(e) => setEmailPermiso(e.currentTarget.value)}
            style={{ flex: 2, minWidth: 200 }}
          />
          <Select
            label="Nivel"
            value={nivel}
            onChange={setNivel}
            data={[
              { value: "LECTURA", label: "Lectura" },
              { value: "EDICION", label: "Edición" },
              { value: "ADMINISTRACION", label: "Administración" },
            ]}
            style={{ flex: 1, minWidth: 140 }}
          />
          <Button onClick={() => asignarPermiso.mutate()} loading={asignarPermiso.isPending} disabled={!emailPermiso}>
            Asignar
          </Button>
        </Group>
        {asignarPermiso.isSuccess && <Alert color="green">Permiso asignado.</Alert>}
        {asignarPermiso.error && <Alert color="red">{asignarPermiso.error.message}</Alert>}
      </Stack>
    </Card>
  );
}