"""프롬프트 템플릿 엔진 테스트.

prompts.yaml 로딩, 변수 치환, 에러 처리 검증.
"""

from unittest.mock import patch

import pytest

from src.config.prompts import (
    PromptTemplate,
    PromptsConfig,
    load_prompts_config,
)
from src.services.prompt_engine import render_system_prompt


# --- PromptsConfig 데이터 클래스 테스트 ---


class TestPromptsConfig:
    """PromptsConfig 및 PromptTemplate 데이터 클래스 테스트."""

    def test_prompt_template_creation(self):
        """PromptTemplate 기본 생성 테스트."""
        template = PromptTemplate(
            name="summary",
            system="약 {target_n_tokens} 토큰으로 요약하세요.",
            variables={"target_n_tokens": 300},
        )
        assert template.name == "summary"
        assert "{target_n_tokens}" in template.system
        assert template.variables["target_n_tokens"] == 300

    def test_prompts_config_get_template(self):
        """템플릿 이름으로 조회 테스트."""
        template = PromptTemplate(
            name="summary",
            system="test",
            variables={},
        )
        config = PromptsConfig(templates={"summary": template})

        assert config.get_template("summary") is template
        assert config.get_template("nonexistent") is None

    def test_prompt_template_frozen(self):
        """frozen dataclass 불변성 테스트."""
        template = PromptTemplate(
            name="summary",
            system="test",
            variables={},
        )
        with pytest.raises(AttributeError):
            template.name = "changed"


# --- prompts.yaml 로딩 테스트 ---


class TestLoadPromptsConfig:
    """prompts.yaml 로딩 테스트."""

    def test_load_prompts_config_success(self):
        """정상 로딩 테스트."""
        load_prompts_config.cache_clear()
        config = load_prompts_config()

        assert isinstance(config, PromptsConfig)
        assert "summary" in config.templates
        assert "key_extraction" in config.templates

    def test_summary_template_has_required_fields(self):
        """summary 템플릿 필수 필드 검증."""
        load_prompts_config.cache_clear()
        config = load_prompts_config()
        template = config.get_template("summary")

        assert template is not None
        assert "{target_n_tokens}" in template.system
        assert "target_n_tokens" in template.variables
        assert isinstance(template.variables["target_n_tokens"], int)

    def test_file_not_found_raises_error(self, tmp_path):
        """파일 미존재 시 FileNotFoundError 발생."""
        load_prompts_config.cache_clear()
        with patch(
            "src.config.prompts.PROMPTS_CONFIG_PATH",
            tmp_path / "nonexistent.yaml",
        ):
            with pytest.raises(FileNotFoundError, match="필수 설정 파일"):
                load_prompts_config()

    def test_missing_system_field_raises_error(self, tmp_path):
        """system 필드 누락 시 ValueError 발생."""
        load_prompts_config.cache_clear()
        bad_yaml = tmp_path / "prompts.yaml"
        bad_yaml.write_text(
            "summary:\n  target_n_tokens: 300\n",
            encoding="utf-8",
        )
        with patch(
            "src.config.prompts.PROMPTS_CONFIG_PATH",
            bad_yaml,
        ):
            with pytest.raises(ValueError, match="system.*누락"):
                load_prompts_config()


# --- 템플릿 엔진 렌더링 테스트 ---


class TestRenderSystemPrompt:
    """render_system_prompt 함수 테스트."""

    def test_render_with_config_variables(self):
        """config 변수로 정상 렌더링."""
        load_prompts_config.cache_clear()
        result = render_system_prompt("summary")

        assert "300" in result
        assert "{target_n_tokens}" not in result

    def test_render_with_override(self):
        """override로 변수 덮어쓰기."""
        load_prompts_config.cache_clear()
        result = render_system_prompt("summary", target_n_tokens=500)

        assert "500" in result
        assert "300" not in result

    def test_render_key_extraction(self):
        """key_extraction 템플릿 렌더링."""
        load_prompts_config.cache_clear()
        result = render_system_prompt("key_extraction")

        assert "200" in result
        assert "{target_n_tokens}" not in result

    def test_nonexistent_template_raises_error(self):
        """존재하지 않는 템플릿 조회 시 ValueError."""
        load_prompts_config.cache_clear()
        with pytest.raises(ValueError, match="찾을 수 없습니다"):
            render_system_prompt("nonexistent")

    def test_missing_variable_raises_error(self):
        """필수 변수 누락 시 ValueError."""
        load_prompts_config.cache_clear()
        template = PromptTemplate(
            name="test",
            system="{missing_var} 테스트",
            variables={},
        )
        config = PromptsConfig(templates={"test": template})

        with patch(
            "src.services.prompt_engine.get_prompt_template",
            side_effect=lambda name: config.get_template(name),
        ):
            with pytest.raises(ValueError, match="필수 변수가 누락"):
                render_system_prompt("test")
