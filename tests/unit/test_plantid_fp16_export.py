"""fp16 weight storage: half the bytes, fp32 in and out, same outputs to fp16 precision."""
import numpy as np
import pytest

onnx = pytest.importorskip('onnx')
ort = pytest.importorskip('onnxruntime')

from onnx import TensorProto, helper, numpy_helper  # noqa: E402

from ml.training.export_plantid_onnx import _to_fp16_weights  # noqa: E402


def _tiny_model(path):
    rng = np.random.default_rng(0)
    w = numpy_helper.from_array(rng.normal(size=(64, 32)).astype(np.float32), 'w')
    b = numpy_helper.from_array(rng.normal(size=32).astype(np.float32), 'b')
    shape = numpy_helper.from_array(np.array([-1, 32], dtype=np.int64), 'shape')   # non-float: left alone
    graph = helper.make_graph(
        [helper.make_node('MatMul', ['pixels', 'w'], ['mm']),
         helper.make_node('Add', ['mm', 'b'], ['sum']),
         helper.make_node('Reshape', ['sum', 'shape'], ['embedding'])],
        'tiny',
        [helper.make_tensor_value_info('pixels', TensorProto.FLOAT, [None, 64])],
        [helper.make_tensor_value_info('embedding', TensorProto.FLOAT, [None, 32])],
        [w, b, shape])
    # IR 8 = what torch.onnx writes at opset 17; newer onnx defaults past what onnxruntime loads.
    onnx.save(helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)], ir_version=8), str(path))


def _run(path, x):
    return ort.InferenceSession(str(path), providers=['CPUExecutionProvider']).run(None, {'pixels': x})[0]


def test_fp16_weights_match_fp32_and_halve_the_file(tmp_path):
    fp32, fp16 = tmp_path / 'fp32.onnx', tmp_path / 'fp16.onnx'
    _tiny_model(fp32)
    _to_fp16_weights(fp32, fp16)

    x = np.random.default_rng(1).normal(size=(4, 64)).astype(np.float32)
    a, b = _run(fp32, x), _run(fp16, x)
    assert b.dtype == np.float32                      # clients keep feeding/reading fp32
    np.testing.assert_allclose(a, b, rtol=1e-2, atol=1e-2)
    assert fp16.stat().st_size < 0.6 * fp32.stat().st_size

    inits = {i.name: i.data_type for i in onnx.load(str(fp16)).graph.initializer}
    assert inits == {'w_fp16': TensorProto.FLOAT16, 'b_fp16': TensorProto.FLOAT16, 'shape': TensorProto.INT64}
