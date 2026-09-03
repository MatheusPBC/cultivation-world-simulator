from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass(slots=True)
class GameQueryDependencies:
    static_data: Any
    runtime: Any
    avatar_assets: dict[str, Any]
    config: Any
    model_to_dict: Any
    get_runtime_run_config: Any
    resolve_avatar_action_emoji: Any
    resolve_avatar_pic_id: Any
    serialize_events_for_client: Any
    serialize_active_domains: Any
    serialize_phenomenon: Any
    get_world_state: Any
    get_world_map: Any
    get_map_presets_query: Any
    get_runtime_status: Any
    get_events_page: Any
    get_world_journal_query: Any
    get_live_guide_query: Any
    ask_live_guide_query: Any
    get_event_causal_detail_query: Any
    get_world_chronicle_query: Any
    get_chronicle_dossier_query: Any
    get_game_data_query: Any
    realm_order: Any
    alignment_enum: Any
    get_detail_query: Any
    build_sect_detail: Any
    language_manager: Any
    build_avatar_adjust_options: Any
    get_avatar_assets_meta_query: Any
    get_avatar_list_query: Any
    get_phenomena_list_query: Any
    get_sect_territories_summary_query: Any
    list_saves_query: Any
    get_list_saves: Any
    get_rankings_query: Any
    get_sect_relations_query: Any
    compute_sect_relations: Any
    get_mortal_overview_query: Any
    build_mortal_overview: Any
    get_dynasty_overview_query: Any
    build_dynasty_overview: Any
    get_dynasty_detail_query: Any
    build_dynasty_detail: Any
    get_avatar_overview_query: Any
    get_deceased_list_query: Any
    get_roleplay_session_query: Any
    get_world_secret_meta_query: Any
    get_world_secret_overview_query: Any


class GameQueryService:
    """Public-query use-case service.

    The old builder namespace is retained only as a compatibility adapter for
    legacy tests and imports. Public routers should call this service directly.
    """

    def __init__(self, dependencies: GameQueryDependencies):
        self._deps = dependencies

    @classmethod
    def from_dependencies(cls, *, static_data: Any, **dependencies: Any) -> "GameQueryService":
        return cls(GameQueryDependencies(static_data=static_data, **dependencies))

    @property
    def builders(self) -> Any:
        return SimpleNamespace(
            build_public_world_state=self.get_world_state,
            build_public_world_map=self.get_world_map,
            build_public_map_presets=self.get_map_presets,
            build_public_runtime_status=self.get_runtime_status,
            build_public_current_run=self.get_current_run,
            build_public_events_page=self.get_events_page,
            build_public_world_journal=self.get_world_journal,
            build_public_live_guide=self.get_live_guide,
            build_public_live_guide_answer=self.ask_live_guide,
            build_public_event_causal_detail=self.get_event_causal_detail,
            build_public_world_chronicle=self.get_world_chronicle,
            build_public_chronicle_dossier=self.get_chronicle_dossier,
            build_public_game_data=self.get_game_data,
            build_public_detail=self.get_detail,
            build_public_avatar_adjust_options=self.get_avatar_adjust_options,
            build_public_avatar_meta=self.get_avatar_meta,
            build_public_avatar_list=self.get_avatar_list,
            build_public_phenomena=self.get_phenomena,
            build_public_sect_territories=self.get_sect_territories,
            build_public_saves=self.get_saves,
            build_public_rankings=self.get_rankings,
            build_public_sect_relations=self.get_sect_relations,
            build_public_mortal_overview=self.get_mortal_overview,
            build_public_dynasty_overview=self.get_dynasty_overview,
            build_public_dynasty_detail=self.get_dynasty_detail,
            build_public_dao_petitions=self.get_dao_petitions,
            build_public_avatar_overview=self.get_avatar_overview,
            build_public_deceased_list=self.get_deceased_list,
            build_public_roleplay_session=self.get_roleplay_session,
            build_public_world_secret_meta=self.get_world_secret_meta,
            build_public_world_secret_overview=self.get_world_secret_overview,
        )

    def _resolve_avatar_pic_id(self, avatar: Any) -> int:
        return self._deps.resolve_avatar_pic_id(
            avatar_assets=self._deps.avatar_assets,
            avatar=avatar,
        )

    def get_runtime_status(self) -> dict:
        return self._deps.get_runtime_status(
            self._deps.runtime,
            getattr(getattr(self._deps.config, "meta", None), "version", ""),
        )

    def get_world_state(self) -> dict:
        return self._deps.get_world_state(
            self._deps.runtime,
            resolve_avatar_action_emoji=self._deps.resolve_avatar_action_emoji,
            resolve_avatar_pic_id=self._resolve_avatar_pic_id,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            serialize_active_domains=self._deps.serialize_active_domains,
            serialize_phenomenon=self._deps.serialize_phenomenon,
        )

    def get_world_map(self) -> dict:
        return self._deps.get_world_map(
            self._deps.runtime,
            sects_by_id=self._deps.static_data.sects_by_id,
            render_config=self._deps.config.get("frontend_defaults", {}),
        )

    def get_world_semantic_model(self) -> dict:
        from src.server.services.game_queries import get_world_semantic_model

        return get_world_semantic_model(self._deps.runtime)

    def get_map_presets(self, *, locale: str | None = None) -> dict:
        return self._deps.get_map_presets_query(locale=locale)

    def get_current_run(self) -> dict:
        return self._deps.model_to_dict(self._deps.get_runtime_run_config(self._deps.runtime))

    def get_events_page(
        self,
        *,
        avatar_id: str | None,
        avatar_id_1: str | None,
        avatar_id_2: str | None,
        sect_id: int | None,
        major_scope: str,
        cursor: str | None,
        limit: int,
    ) -> dict:
        return self._deps.get_events_page(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            avatar_id=avatar_id,
            avatar_id_1=avatar_id_1,
            avatar_id_2=avatar_id_2,
            sect_id=sect_id,
            major_scope=major_scope,
            cursor=cursor,
            limit=limit,
        )

    def get_world_journal(self, *, period_months: int) -> dict:
        return self._deps.get_world_journal_query(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            period_months=period_months,
        )

    def get_live_guide(self) -> dict:
        return self._deps.get_live_guide_query(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
        )

    async def ask_live_guide(self, *, question: str) -> dict:
        return await self._deps.ask_live_guide_query(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            question=question,
        )

    def get_event_causal_detail(self, *, event_id: str, depth: int, limit: int) -> dict:
        return self._deps.get_event_causal_detail_query(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            event_id=event_id,
            depth=depth,
            limit=limit,
        )

    def get_world_chronicle(self, *, cursor: str | None, limit: int) -> dict:
        return self._deps.get_world_chronicle_query(
            self._deps.runtime,
            cursor=cursor,
            limit=limit,
        )

    def get_chronicle_dossier(
        self,
        *,
        chapter_id: str,
        anchor_id: str,
        depth: int,
        limit: int,
    ) -> dict:
        return self._deps.get_chronicle_dossier_query(
            self._deps.runtime,
            serialize_events_for_client=self._deps.serialize_events_for_client,
            chapter_id=chapter_id,
            anchor_id=anchor_id,
            depth=depth,
            limit=limit,
        )

    def get_rankings(self) -> dict:
        return self._deps.get_rankings_query(self._deps.runtime)

    def get_sect_relations(self) -> dict:
        return self._deps.get_sect_relations_query(
            self._deps.runtime,
            compute_sect_relations=self._deps.compute_sect_relations,
        )

    def get_game_data(self) -> dict:
        static_data = self._deps.static_data
        return self._deps.get_game_data_query(
            sects_by_id=static_data.sects_by_id,
            races_by_id=static_data.races_by_id,
            personas_by_id=static_data.personas_by_id,
            realm_order=self._deps.realm_order,
            techniques_by_id=static_data.techniques_by_id,
            weapons_by_id=static_data.weapons_by_id,
            auxiliaries_by_id=static_data.auxiliaries_by_id,
            alignment_enum=self._deps.alignment_enum,
        )

    def get_avatar_adjust_options(self) -> dict:
        return self._deps.build_avatar_adjust_options()

    def get_avatar_meta(self) -> dict:
        return self._deps.get_avatar_assets_meta_query(avatar_assets=self._deps.avatar_assets)

    def get_avatar_list(self) -> dict:
        return self._deps.get_avatar_list_query(self._deps.runtime)

    def get_phenomena(self) -> dict:
        return self._deps.get_phenomena_list_query(
            celestial_phenomena_by_id=self._deps.static_data.celestial_phenomena_by_id,
            serialize_phenomenon=self._deps.serialize_phenomenon,
        )

    def get_sect_territories(self) -> dict:
        return self._deps.get_sect_territories_summary_query(self._deps.runtime)

    def get_mortal_overview(self) -> dict:
        return self._deps.get_mortal_overview_query(
            self._deps.runtime,
            build_mortal_overview=self._deps.build_mortal_overview,
        )

    def get_dynasty_overview(self) -> dict:
        return self._deps.get_dynasty_overview_query(
            self._deps.runtime,
            build_dynasty_overview=self._deps.build_dynasty_overview,
        )

    def get_dynasty_detail(self) -> dict:
        return self._deps.get_dynasty_detail_query(
            self._deps.runtime,
            build_dynasty_detail=self._deps.build_dynasty_detail,
        )

    def get_dao_petitions(self) -> dict:
        world = self._deps.runtime.get("world")
        petitions = list(getattr(world, "dao_petitions", []) or []) if world is not None else []

        def serialize(petition):
            data = petition.to_dict()
            initiator_kind = str(getattr(petition, "initiator_kind", "") or "")
            initiator_id = str(getattr(petition, "initiator_id", "") or "")
            initiator_name = ""
            if world is not None and initiator_kind == "avatar":
                avatar = world.avatar_manager.get_avatar(initiator_id)
                initiator_name = str(getattr(avatar, "name", "") or "")
            elif world is not None and initiator_kind == "sect":
                sect = next((item for item in getattr(world, "existed_sects", []) or [] if str(getattr(item, "id", "")) == initiator_id), None)
                initiator_name = str(getattr(sect, "name", "") or "")
            elif world is not None and initiator_kind == "court":
                dynasty = getattr(world, "dynasty", None)
                initiator_name = str(getattr(dynasty, "title", "") or getattr(dynasty, "name", "") or "")
            data["initiator_name"] = initiator_name
            response_event = world.event_manager.get_event_by_id(petition.response_event_id) if world is not None and petition.response_event_id else None
            data["response_content"] = str(getattr(response_event, "content", "") or "")
            return data

        return {
            "pending": [serialize(item) for item in petitions if item.status.value == "pending"],
            "history": [serialize(item) for item in petitions if item.status.value != "pending"],
        }

    def get_avatar_overview(self) -> dict:
        return self._deps.get_avatar_overview_query(self._deps.runtime)

    def get_saves(self) -> dict:
        return self._deps.list_saves_query(list_saves=self._deps.get_list_saves())

    def get_detail(self, *, target_type: str, target_id: str) -> dict:
        return self._deps.get_detail_query(
            self._deps.runtime,
            target_type=target_type,
            target_id=target_id,
            sects_by_id=self._deps.static_data.sects_by_id,
            build_sect_detail=self._deps.build_sect_detail,
            language_manager=self._deps.language_manager,
            resolve_avatar_pic_id=self._resolve_avatar_pic_id,
        )

    def get_deceased_list(self) -> dict:
        return self._deps.get_deceased_list_query(self._deps.runtime)

    def get_roleplay_session(self) -> dict:
        return self._deps.get_roleplay_session_query(self._deps.runtime)

    def get_world_secret_meta(self) -> dict:
        return self._deps.get_world_secret_meta_query()

    def get_world_secret_overview(self) -> dict:
        return self._deps.get_world_secret_overview_query(self._deps.runtime)
