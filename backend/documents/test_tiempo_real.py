from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels_redis.core import RedisChannelLayer


def test_channel_layer_redis_ida_y_vuelta():
    capa = get_channel_layer()
    # Debe ser Redis, no la capa en memoria: el estado tiene que poder
    # compartirse entre procesos.
    assert isinstance(capa, RedisChannelLayer)

    async def ida_y_vuelta():
        canal = await capa.new_channel()
        await capa.send(canal, {"type": "prueba", "texto": "hola"})
        return await capa.receive(canal)

    mensaje = async_to_sync(ida_y_vuelta)()

    assert mensaje == {"type": "prueba", "texto": "hola"}
