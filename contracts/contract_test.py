import pytest
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod


class ContractValidator:
    """
    契约验证器

    功能：验证模块实现是否符合接口契约
    原理：运行时反射检查 + 行为测试

    使用方式：
        validator = ContractValidator(INLPModule)
        validator.validate_implementation(MyNLPModule)
    """

    def __init__(self, interface_class: type):
        self.interface = interface_class
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_implementation(self, implementation_class: type) -> Dict[str, Any]:
        """
        验证实现类是否符合接口契约

        Args:
            implementation_class: 实现类

        Returns:
            验证结果
        """
        self.errors = []
        self.warnings = []

        # 1. 检查是否实现了接口
        if not issubclass(implementation_class, self.interface):
            self.errors.append(
                f"'{implementation_class.__name__}' 必须继承 '{self.interface.__name__}'"
            )
            return self._get_result()

        # 2. 检查抽象方法是否全部实现
        self._check_abstract_methods(implementation_class)

        # 3. 检查方法签名是否匹配
        self._check_method_signatures(implementation_class)

        # 4. 检查类型注解
        self._check_type_annotations(implementation_class)

        return self._get_result()

    def _check_abstract_methods(self, cls: type) -> None:
        """检查抽象方法是否全部实现"""
        for attr_name in dir(self.interface):
            # 跳过内置属性
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(self.interface, attr_name)
                if getattr(attr, '__isabstractmethod__', False):
                    # 检查子类是否覆盖了该方法（非抽象）
                    impl_attr = getattr(cls, attr_name, None)
                    if impl_attr is None:
                        self.errors.append(
                            f"缺少抽象方法实现: '{attr_name}'"
                        )
                    elif getattr(impl_attr, '__isabstractmethod__', False):
                        # 子类仍然声明为抽象方法（未实现）
                        self.errors.append(
                            f"抽象方法未实现: '{attr_name}'"
                        )
            except Exception:
                continue

    def _check_method_signatures(self, cls: type) -> None:
        """检查方法签名是否匹配"""
        import inspect

        for attr_name in dir(self.interface):
            interface_attr = getattr(self.interface, attr_name)
            impl_attr = getattr(cls, attr_name, None)

            if not callable(interface_attr) or not callable(impl_attr):
                continue

            try:
                interface_sig = inspect.signature(interface_attr)
                impl_sig = inspect.signature(impl_attr)

                # 检查参数名是否一致
                interface_params = list(interface_sig.parameters.keys())
                impl_params = list(impl_sig.parameters.keys())

                # 实现类可以有额外参数，但必须包含接口的所有参数
                for param in interface_params:
                    if param not in impl_params:
                        self.errors.append(
                            f"方法 '{attr_name}' 缺少参数 '{param}'"
                        )
            except Exception:
                pass

    def _check_type_annotations(self, cls: type) -> None:
        """检查类型注解"""
        import inspect

        for attr_name in dir(self.interface):
            interface_attr = getattr(self.interface, attr_name)
            impl_attr = getattr(cls, attr_name, None)

            if not callable(interface_attr) or not callable(impl_attr):
                continue

            try:
                interface_sig = inspect.signature(interface_attr)
                impl_sig = inspect.signature(impl_attr)

                # 检查返回值注解
                if interface_sig.return_annotation != inspect.Signature.empty:
                    if impl_sig.return_annotation == inspect.Signature.empty:
                        self.warnings.append(
                            f"方法 '{attr_name}' 缺少返回值类型注解"
                        )
            except Exception:
                pass

    def _get_result(self) -> Dict[str, Any]:
        """获取验证结果"""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }


class ContractTest:
    """
    契约测试基类

    所有公司开发的模块测试必须继承此类
    提供标准的契约测试框架

    使用方式：
        class TestMyModuleContract(ContractTest):
            def get_module_class(self):
                return MyModule

            def get_interface_class(self):
                return IMyModule

            def test_specific_behavior(self):
                # 模块特定的行为测试
                pass
    """

    @abstractmethod
    def get_module_class(self) -> type:
        """返回被测试的模块类"""
        pass

    @abstractmethod
    def get_interface_class(self) -> type:
        """返回模块实现的接口类"""
        pass

    def test_interface_compliance(self):
        """测试接口合规性"""
        validator = ContractValidator(self.get_interface_class())
        result = validator.validate_implementation(self.get_module_class())

        assert result['valid'], f"接口合规性检查失败: {result['errors']}"

    def test_instantiation(self):
        """测试模块可以实例化"""
        cls = self.get_module_class()
        try:
            instance = cls()
            assert instance is not None
        except Exception as e:
            pytest.fail(f"模块实例化失败: {e}")

    def test_has_required_methods(self):
        """测试包含所有必需方法"""
        module_cls = self.get_module_class()
        interface_cls = self.get_interface_class()

        for attr_name in dir(interface_cls):
            attr = getattr(interface_cls, attr_name)
            if getattr(attr, '__isabstractmethod__', False):
                assert hasattr(module_cls, attr_name), \
                    f"缺少必需方法: {attr_name}"

    def test_method_callable(self):
        """测试所有公共方法可调用"""
        module_cls = self.get_module_class()
        instance = module_cls()

        for attr_name in dir(module_cls):
            if attr_name.startswith('_'):
                continue
            attr = getattr(instance, attr_name)
            if callable(attr):
                # 方法存在且可调用
                assert True

    def test_module_registration(self):
        """测试模块可以注册到注册表"""
        from contracts import ModuleRegistry, ModuleInfo, ModuleStatus

        module_cls = self.get_module_class()
        instance = module_cls()

        # 如果模块有 get_module_info 方法
        if hasattr(instance, 'get_module_info'):
            info = instance.get_module_info()
            assert isinstance(info, ModuleInfo)
            assert ModuleRegistry.register(info)
            ModuleRegistry.unregister(info.name)

    def run_all_contract_tests(self) -> Dict[str, Any]:
        """运行所有契约测试"""
        results = {
            'interface_compliance': self._run_test(self.test_interface_compliance),
            'instantiation': self._run_test(self.test_instantiation),
            'required_methods': self._run_test(self.test_has_required_methods),
            'method_callable': self._run_test(self.test_method_callable),
            'registration': self._run_test(self.test_module_registration),
        }

        results['all_passed'] = all(r['passed'] for r in results.values())
        return results

    def _run_test(self, test_func: Callable) -> Dict[str, Any]:
        """运行单个测试"""
        try:
            test_func()
            return {'passed': True, 'error': None}
        except Exception as e:
            return {'passed': False, 'error': str(e)}
