# 연결 규약 스키마

규약 폴더 안의 모든 `.json`을 합쳐서 읽는다. 각 파일은 아래 종류 중 일부만 담아도 된다.
같은 종류에서 `id`는 폴더 전체에서 하나여야 한다.

## 항목이 서로 이어지는 방식

```
slots ◄── parts ──► skeletons ◄── ik_profiles
                       ▲   ▲
        characters ────┘   └──── mounts ──► seats ──► anim_sets(탑승자)
            │                      │
            ├──► anim_sets ◄───────┤
            └──► movement_modes ◄──┘ ◄── weather(blocked_modes) ◄── biomes
parts.vfx / mounts.vfx / weather.vfx ──► vfx
```

핵심은 `movement_modes`다. 모드 하나가 "이 모드를 쓰려면 필요한 애니메이션 상태", "탑승자에게 필요한 상태",
"발 IK 사용 여부", "갈 수 있는 다른 모드"를 정한다. 캐릭터와 탈것은 쓸 모드를 고르기만 한다.
그래서 새 이동 방식을 추가하면 그것을 쓰는 모든 캐릭터와 탈것에 필요한 것이 자동으로 계산된다.

## 종류별 필드

### skeletons
| 필드 | 설명 |
|---|---|
| `id` | 스켈레톤 이름 |
| `sockets` | 부착에 쓰는 소켓 이름 목록 |
| `ik_profile` | 이 스켈레톤의 IK 프로필 id |

### ik_profiles
| 필드 | 설명 |
|---|---|
| `skeleton` | 대상 스켈레톤 |
| `foot_placement` | 발 배치 IK를 지원하는가 |
| `chains` | IK 체인 이름 목록 (참고용) |

### slots
장착 부위. `id`만 있다.

### parts
| 필드 | 설명 |
|---|---|
| `slot` | 차지하는 부위 |
| `skeleton` | 맞는 스켈레톤 |
| `covers` | 함께 가리는 부위 (전신 로브가 다리를 가림) |
| `requires_sockets` | 스켈레톤에 있어야 하는 소켓 |
| `provides_sockets` | 이 파츠가 새로 제공하는 소켓 (칼끝, 망토 끝) |
| `tags` | 분류 태그 |
| `vfx` | `[{effect, socket}]`. 소켓은 스켈레톤 소켓이거나 이 파츠가 제공하는 소켓 |

### movement_modes
| 필드 | 설명 |
|---|---|
| `required_states` | 이 모드를 쓰는 주체의 애니메이션 세트에 있어야 하는 상태 |
| `rider_states` | 이 모드를 쓰는 탈것에 탄 사람의 애니메이션 세트에 있어야 하는 상태 |
| `foot_ik` | 발 배치 IK를 쓰는가 |
| `airborne` | 공중 모드인가 |
| `transitions` | 이 모드에서 갈 수 있는 모드 |

### anim_sets
| 필드 | 설명 |
|---|---|
| `skeleton` | 대상 스켈레톤 |
| `states` | 제공하는 상태 이름 목록 |

### characters
| 필드 | 설명 |
|---|---|
| `skeleton`, `anim_set` | 몸과 기본 애니메이션 세트 |
| `modes` | 쓸 수 있는 이동 모드 |
| `default_mode` | 기본 모드. 모든 모드는 여기서 갈 수 있고 여기로 돌아올 수 있어야 한다 |

### mounts
캐릭터의 필드에 더해:

| 필드 | 설명 |
|---|---|
| `seats` | `[{socket, rider_anim_set, rider_ik_sockets}]`. 탑승자 애니메이션 세트의 스켈레톤이 캐릭터 스켈레톤과 같아야 그 캐릭터가 탈 수 있다 |
| `rider_hidden_slots` | 탔을 때 숨길 탑승자 파츠 부위 (날개와 겹치는 망토 등) |
| `vfx` | `[{effect, socket, mode}]`. `mode`가 있으면 그 모드에서만 켜진다 |

### vfx
| 필드 | 설명 |
|---|---|
| `category` | part / mount / weather / skill / ambient |
| `cost` | 예산 점수. 프로젝트가 정한 단위 |
| `pooled` | 풀링 사용 여부 |
| `attach` | `socket` 또는 `world` |

### weather
| 필드 | 설명 |
|---|---|
| `transitions` | 넘어갈 수 있는 날씨 |
| `params` | 연속 값. 모든 날씨가 같은 키를 가져야 전환 시 보간된다 |
| `vfx` | 켜지는 이펙트 id 목록 |
| `blocked_modes` | 이 날씨에서 못 쓰는 이동 모드 |

### biomes
| 필드 | 설명 |
|---|---|
| `weathers` | 이 지역에 나올 수 있는 날씨 |
| `layers` | `[{asset, density_per_100m2, nanite}]` 배치 레이어 |

### budgets
`vfx_cost_per_part`, `vfx_cost_per_mount`, `biome_density_per_100m2`, `non_nanite_density_per_100m2`.
없는 키는 검사하지 않는다.

## 확장하는 법

| 하고 싶은 것 | 고칠 곳 | 검사기가 알려 주는 것 |
|---|---|---|
| 새 파츠 | `parts`에 한 줄 | 없는 부위, 없는 소켓, 이펙트 예산 초과 |
| 새 장착 부위 | `slots`에 한 줄 | 없음. 이후 파츠가 참조할 수 있게 된다 |
| 새 탈것 | `mounts`, 필요하면 `skeletons`, `anim_sets`, `ik_profiles` | 빠진 상태, 좌석 소켓, 탈 수 있는 캐릭터 유무 |
| 기존 탈것에 비행 추가 | 탈것의 `modes`에 `fly` | 탈것과 탑승자에게 빠진 비행 상태 |
| 새 이동 방식 (잠수, 벽 타기) | `movement_modes`에 한 줄, 다른 모드의 `transitions`에 연결 | 들어갈 수 없거나 돌아올 수 없는 모드 |
| 새 체형이나 종족 | `skeletons`, `characters`, 탑승자용 `anim_sets` | 그 체형이 탈 수 없는 탈것 (연결 표) |
| 새 날씨 | `weather`에 한 줄, 다른 날씨의 `transitions`에 연결 | 빠진 파라미터, 고립된 날씨, 비행 금지 시 내려올 길 |
| 새 지역 | `biomes`에 한 줄 | 없는 날씨, 밀도 예산 초과 |

새 종류의 연결이 필요하면(예: 탈것 전용 파츠) `check_contract.py`의 `KINDS`와 `check()`에 추가하고
테스트를 붙인다. 기존 데이터 파일은 고치지 않아도 된다.
