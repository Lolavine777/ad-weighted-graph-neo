/* Published evidence playback; source details in README.md. No search results are synthesized. */
globalThis.NEO_DEMOS = {
  paths: {
    version: "neo-viewer-playback/1",
    title: "SEAMLESS · Top-3 theo C",
    source: "QUEEN_COX@SEAMLESS.INTERNAL",
    target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
    context: "BADBLOOD.SEAMLESS.INTERNAL",
    labels: {
      "QUEEN_COX@SEAMLESS.INTERNAL": {
        label: "QUEEN_COX",
        kind: "User",
        x: 110,
        y: 340,
      },
      "DOMAIN USERS@SEAMLESS.INTERNAL": {
        label: "DOMAIN USERS",
        kind: "Group",
        x: 320,
        y: 170,
      },
      "AUTHENTICATED USERS@SEAMLESS.INTERNAL": {
        label: "AUTHENTICATED USERS",
        kind: "Group",
        x: 560,
        y: 170,
      },
      "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL": {
        label: "PRE-WINDOWS 2000 COMPATIBLE ACCESS",
        kind: "Group",
        x: 800,
        y: 170,
      },
      "KATRINA_GREEN@SEAMLESS.INTERNAL": {
        label: "KATRINA_GREEN",
        kind: "User",
        x: 800,
        y: 420,
      },
      "BADBLOOD.SEAMLESS.INTERNAL": {
        label: "BADBLOOD",
        kind: "Computer",
        x: 430,
        y: 560,
      },
      "ADMINISTRATORS@SEAMLESS.INTERNAL": {
        label: "ADMINISTRATORS",
        kind: "Group",
        x: 980,
        y: 620,
      },
      "ENTERPRISE ADMINS@SEAMLESS.INTERNAL": {
        label: "ENTERPRISE ADMINS",
        kind: "Group",
        x: 1160,
        y: 420,
      },
    },
    programs: [
      {
        id: "published-path-1",
        C: 4,
        steps: [
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "QUEEN_COX@SEAMLESS.INTERNAL",
            target: "DOMAIN USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "DOMAIN USERS@SEAMLESS.INTERNAL",
            target: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
            target: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Reset mật khẩu",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
            target: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng danh tính vừa reset",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ADMINISTRATORS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Sửa DACL để cấp quyền",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "ADMINISTRATORS@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Thêm thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
        ],
        ledger: [
          {
            technique: "Dùng danh tính vừa reset",
            computed_cost: 0,
            target_id: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique: "Thêm thành viên nhóm",
            computed_cost: 1,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Sửa DACL để cấp quyền",
            computed_cost: 2,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Reset mật khẩu",
            computed_cost: 1,
            target_id: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
        ],
        assumptions: [
          "Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
          "Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
        ],
      },
      {
        id: "published-path-2",
        C: 5,
        steps: [
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "QUEEN_COX@SEAMLESS.INTERNAL",
            target: "DOMAIN USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "DOMAIN USERS@SEAMLESS.INTERNAL",
            target: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
            target: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Reset mật khẩu",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
            target: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng danh tính vừa reset",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ADMINISTRATORS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Sửa DACL để cấp quyền",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "ADMINISTRATORS@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Thêm thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Cấp quyền sửa DACL",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
        ],
        ledger: [
          {
            technique: "Dùng danh tính vừa reset",
            computed_cost: 0,
            target_id: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique: "Thêm thành viên nhóm",
            computed_cost: 1,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Cấp quyền sửa DACL",
            computed_cost: 1,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Sửa DACL để cấp quyền",
            computed_cost: 2,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Reset mật khẩu",
            computed_cost: 1,
            target_id: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
        ],
        assumptions: [
          "Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
          "Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
        ],
      },
      {
        id: "published-path-3",
        C: 5,
        steps: [
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "QUEEN_COX@SEAMLESS.INTERNAL",
            target: "DOMAIN USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "DOMAIN USERS@SEAMLESS.INTERNAL",
            target: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "AUTHENTICATED USERS@SEAMLESS.INTERNAL",
            target: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Reset mật khẩu",
            actor: "QUEEN_COX@SEAMLESS.INTERNAL",
            source: "PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL",
            target: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng danh tính vừa reset",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ADMINISTRATORS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Sửa DACL để cấp quyền",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "ADMINISTRATORS@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Cấp quyền sửa DACL",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Thêm thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique_id: "Dùng quyền thành viên nhóm",
            actor: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            source: "KATRINA_GREEN@SEAMLESS.INTERNAL",
            target: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
        ],
        ledger: [
          {
            technique: "Dùng danh tính vừa reset",
            computed_cost: 0,
            target_id: "BADBLOOD.SEAMLESS.INTERNAL",
          },
          {
            technique: "Thêm thành viên nhóm",
            computed_cost: 1,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Cấp quyền sửa DACL",
            computed_cost: 1,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Sửa DACL để cấp quyền",
            computed_cost: 2,
            target_id: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
          },
          {
            technique: "Reset mật khẩu",
            computed_cost: 1,
            target_id: "KATRINA_GREEN@SEAMLESS.INTERNAL",
          },
        ],
        assumptions: [
          "Xác thực được chấp nhận (`authentication_accepted`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Cho phép sửa đối tượng AD (`directory_write_allowed`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Cho phép thay đổi thành viên nhóm (`membership_change_allowed`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Membership có hiệu lực (`membership_usable`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
          "Kết nối tới KDC (`network_kdc_reachable`): KATRINA_GREEN@SEAMLESS.INTERNAL → BADBLOOD.SEAMLESS.INTERNAL = đúng.",
          "Kết nối RPC tới đích (`network_rpc_reachable`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Mật khẩu mới đáp ứng policy (`password_policy_accepts`): QUEEN_COX@SEAMLESS.INTERNAL → KATRINA_GREEN@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ENTERPRISE ADMINS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): KATRINA_GREEN@SEAMLESS.INTERNAL → ADMINISTRATORS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → AUTHENTICATED USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → DOMAIN USERS@SEAMLESS.INTERNAL = đúng.",
          "Nhóm dùng để cấp quyền bảo mật (`security_group`): QUEEN_COX@SEAMLESS.INTERNAL → PRE-WINDOWS 2000 COMPATIBLE ACCESS@SEAMLESS.INTERNAL = đúng.",
        ],
      },
    ],
    minimum: false,
    truncated: true,
    reason: "path_limit_reached",
    expansions: 51,
    budget: {
      max_paths: 10,
      max_steps: 12,
      max_expansions: 4096,
    },
    provenance: "reports/neo/ranking-C-example.md @ f0e6899",
    source_sha256:
      "7e4a24d6628e22016a6722124aa80b60133827edc3c99c32684652e81f5e5af8",
    notice:
      "Playback từ bản brief đã công bố; không phải lượt search mới. Graph biểu diễn request source → target, actor và context nằm trong chi tiết.",
  },
  remediation: {
    version: "neo-remediation-rediscovery-summary/1",
    base_commit: "c0200ddd19e9e8cbb57d25fde571b47da4e47158",
    evidence_root:
      "reports/generated/neo-remediation-rediscovery-20261023-verified",
    results_sha256:
      "sha256:35a40f558f0cb72d2a84e40ee4eb4f902638e00c5cdb5357ea5ef25c1c115797",
    snapshot_sha256:
      "sha256:bc27b352825266a51607d9b3b6ee322e4d56ee64626a457ba5853c0665c2680b",
    snapshot_id:
      "sha256:10d29ec2b278ecf0b12e51dfaed95333f13c5d14933d3720500f38d6914b2227",
    raw_manifest_sha256:
      "sha256:27a13df4e12582b42b921411150cd0c9ba2b4e3356f0a250fcd992b3cb823062",
    fixed_pack_sha256:
      "sha256:187813032c5ed8f58a79c33549b14bfccf23d1ec7fb8b8a8208d28b02599e229",
    runner_sha256:
      "sha256:dd7ac7ef5830d6f515465feb9c88ac946da6ea0c59dfd52917ca7db14c3d9ef9",
    execution_source_pins_sha256:
      "sha256:2e0cc6852f2f20d89091a9782045bf19b02d3b63dc4f4e213d367400a6245de5",
    scenario:
      "neo-host-session-v1; user usable identity or computer local-admin-only",
    effort_profile: "neo-c-v1",
    effort_profile_sha256:
      "sha256:3c5a9b349768c9bea7463f0d5110fff22969b75bb7090c852c7099a9c2367b7c",
    budget: {
      max_expansions: 4096,
      max_paths: 10,
      max_steps: 12,
    },
    bloodhound: "historical baseline only; no Docker/service calls",
    method:
      "Independent copied-record edits; baseline rebuild must exactly match supplied snapshot; existing parser regenerates inferred edges; native fresh-foothold rediscovery, not old-witness survival.",
    reproduce: [
      ".venv/bin/python",
      "-m",
      "scripts.neo_remediation",
      "--snapshot",
      "reports/generated/neo-remediation-post-localgroup-20261023/inputs/wraith/snapshot.json",
      "--output-dir",
      "reports/generated/neo-remediation-demo-001",
    ],
    prerequisites:
      "Manifest-verified WRAITH raw in data/raw/ad_sampledata or --raw-dir; output directory must be new.",
    cases: [
      {
        case: "rodc-membership",
        removed_observations: {
          Members: 1,
        },
        removed_edges: [
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1119",
            kind: "MemberOf",
            target:
              "domain:sid:S-1-5-21-3702535222-3822678775-2090119576:S-1-5-32-544",
          },
        ],
        updated_derivations: [],
        added_edges: 0,
        queries: [
          {
            strategy: "neo_guided",
            goal: "DA",
            query_sha256:
              "sha256:2d272c8348d4da995a77f46e47dc0b764a143ffa959e1ebcedcfe82c8cc9c557",
            before: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "reachable",
              expansions: 35,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "bypass",
              expansions: 23,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_guided",
            goal: "EA",
            query_sha256:
              "sha256:be4bd5b753cfe61f74d3b0054da195b0119d3e11c116524d937161f2ee98caf6",
            before: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "reachable",
              expansions: 35,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "bypass",
              expansions: 23,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "DA",
            query_sha256:
              "sha256:abee847dd31afebadf74ccf435a6e50f79bf2d6a81b76e60e135b78a8c28be0a",
            before: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "reachable",
              expansions: 4096,
              truncation_reason: "expansion_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {
                directory_write_allowed: 210,
              },
            },
            after: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "bypass",
              expansions: 57,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "EA",
            query_sha256:
              "sha256:c35a165a81e2ba1858edd6633fbdd4bbc494f2b367388e1239199c8b43dec05a",
            before: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "reachable",
              expansions: 4096,
              truncation_reason: "expansion_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {
                directory_write_allowed: 210,
              },
            },
            after: {
              status: "success",
              reached: true,
              C: 3,
              outcome: "bypass",
              expansions: 57,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
        ],
      },
      {
        case: "extca-session",
        removed_observations: {
          PrivilegedSessions: 2,
          RegistrySessions: 1,
        },
        removed_edges: [
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1120",
            kind: "HasSession",
            target: "S-1-5-21-3702535222-3822678775-2090119576-1113",
          },
        ],
        updated_derivations: [],
        added_edges: 0,
        queries: [
          {
            strategy: "neo_guided",
            goal: "DA",
            query_sha256:
              "sha256:bd81c1b6b30fa3c646322d47e440160a588f8e4203f19d5aa15c34552080823f",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 22,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "blocked",
              reached: false,
              C: null,
              outcome: "blocked_in_scope",
              expansions: 3,
              truncation_reason: null,
              minimum_proven: false,
              no_path_proven: true,
              unknown: {},
            },
          },
          {
            strategy: "neo_guided",
            goal: "EA",
            query_sha256:
              "sha256:3d42294b8ee45bfcd8b92373b572a5571fb63f10046a3e50ce4b477191c2bc33",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 22,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "blocked",
              reached: false,
              C: null,
              outcome: "blocked_in_scope",
              expansions: 3,
              truncation_reason: null,
              minimum_proven: false,
              no_path_proven: true,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "DA",
            query_sha256:
              "sha256:fd10584148671912fbae45fd63de46028cbfde6393acb3659d5d4d1f3e8e6cf8",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 25,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "blocked",
              reached: false,
              C: null,
              outcome: "blocked_in_scope",
              expansions: 3,
              truncation_reason: null,
              minimum_proven: false,
              no_path_proven: true,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "EA",
            query_sha256:
              "sha256:f89d89d51c088a2b618be599009da0f655594de2cc5139015b89790f7dc5b03b",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 25,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "blocked",
              reached: false,
              C: null,
              outcome: "blocked_in_scope",
              expansions: 3,
              truncation_reason: null,
              minimum_proven: false,
              no_path_proven: true,
              unknown: {},
            },
          },
        ],
      },
      {
        case: "bm-da-membership",
        removed_observations: {
          Members: 1,
        },
        removed_edges: [
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1113",
            kind: "MemberOf",
            target: "S-1-5-21-3702535222-3822678775-2090119576-512",
          },
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1113",
            kind: "AdminTo",
            target: "S-1-5-21-3702535222-3822678775-2090119576-11203",
          },
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1113",
            kind: "AdminTo",
            target: "S-1-5-21-3702535222-3822678775-2090119576-1120",
          },
        ],
        updated_derivations: [
          {
            source: "S-1-5-21-3702535222-3822678775-2090119576-1113",
            kind: "AdminTo",
            target: "S-1-5-21-3702535222-3822678775-2090119576-1000",
            before_paths: 2,
            after_paths: 1,
          },
        ],
        added_edges: 0,
        queries: [
          {
            strategy: "neo_guided",
            goal: "DA",
            query_sha256:
              "sha256:bd81c1b6b30fa3c646322d47e440160a588f8e4203f19d5aa15c34552080823f",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 22,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 5,
              outcome: "bypass",
              expansions: 49,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_guided",
            goal: "EA",
            query_sha256:
              "sha256:3d42294b8ee45bfcd8b92373b572a5571fb63f10046a3e50ce4b477191c2bc33",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 22,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "bypass",
              expansions: 23,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "DA",
            query_sha256:
              "sha256:fd10584148671912fbae45fd63de46028cbfde6393acb3659d5d4d1f3e8e6cf8",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 25,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 5,
              outcome: "bypass",
              expansions: 4096,
              truncation_reason: "expansion_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
          {
            strategy: "neo_refine",
            goal: "EA",
            query_sha256:
              "sha256:f89d89d51c088a2b618be599009da0f655594de2cc5139015b89790f7dc5b03b",
            before: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "reachable",
              expansions: 25,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
            after: {
              status: "success",
              reached: true,
              C: 2,
              outcome: "bypass",
              expansions: 26,
              truncation_reason: "path_limit_reached",
              minimum_proven: false,
              no_path_proven: false,
              unknown: {},
            },
          },
        ],
      },
    ],
    validation: {
      queries: 24,
      witnesses_replayed: 200,
      C_ledgers_checked: 200,
      related_tests_passed: 251,
      related_tests_skipped: 0,
      full_suite_run: false,
      tests_log:
        "reports/generated/neo-remediation-rediscovery-tests-final.log",
      tests_log_sha256:
        "sha256:910b8e130cbcf95497059932d3c113ea247cefb74f4dcd99cda3effce4d79c82",
      ruff: "check and format check passed for new runner/tests",
      diff_check: "passed",
      independent_artifact_audit:
        "reports/generated/neo-remediation-rediscovery-audit.json",
      audit_sha256:
        "sha256:9d239de9f6f058266b4ce5687992918615f1b0a3f7588ab3bae3867a18eb87e9",
      before_after_query_identical: true,
      strategies_differ_only_in_search_order: true,
      snapshots_reloadable: true,
      baseline_unchanged: true,
    },
    limits: [
      "All successful runs are capped best-found, not globally minimum C.",
      "RODCMANAGER neo_refine before each goal: expansion cap and 210 directory_write_allowed Unknown attempts; C=3 witness remains valid.",
      "BM membership removal, DA neo_refine: expansion cap at 4096, valid C=5 bypass.",
      "Session removal: four complete, non-truncated no-path results, 3 expansions each, no Unknown; blocked only within declared local-admin-only scope.",
      "Fresh foothold does not retain previously stolen credentials; removing a session does not revoke them.",
      "Same previously inspected WRAITH dataset; no blind test or new BloodHound comparison.",
      "Legacy projection-only remediation helpers are unchanged; use this record-rebuild demo for these three cases.",
    ],
  },
};
if (typeof module !== "undefined") module.exports = globalThis.NEO_DEMOS;

globalThis.NEO_DEMOS.survey = {
  schema_version: "neo-decision-sample/1.0.0",
  execution_parent_commit: "ee4dcada2b1677a7997ce0428054dcbc07ebc5d6",
  scope: {
    request: {
      batch_id: "auto-exposure",
      common_budget: {
        max_expansions: 1024,
        max_paths: 3,
        max_steps: 12,
      },
      evaluation_mode: "scenario",
      prioritization_policy: "min_effort_impact_pareto",
      schema_version: "batch-query-request/1.1.0",
      snapshot_id:
        "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812",
      sources: [
        {
          authentication_context:
            "S-1-5-21-1271839998-3495686680-2211690266-1000",
          custom_budget: null,
          declared_assumptions: [],
          description:
            "Independent declared compromise scenario; not observed compromise",
          node_id: "S-1-5-21-1271839998-3495686680-2211690266-1815",
          node_kind: "User",
          profile_kind: "user_usable_identity",
          source_id:
            "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
        },
        {
          authentication_context:
            "S-1-5-21-1271839998-3495686680-2211690266-1000",
          custom_budget: null,
          declared_assumptions: [],
          description:
            "Independent declared compromise scenario; not observed compromise",
          node_id: "S-1-5-21-1271839998-3495686680-2211690266-2091",
          node_kind: "User",
          profile_kind: "user_usable_identity",
          source_id:
            "source-user-62fb91f2c503d49e7af991a5739a2fcc4d30e3a5e5ab9ca99730cd47d20753b6",
        },
        {
          authentication_context:
            "S-1-5-21-1271839998-3495686680-2211690266-1000",
          custom_budget: null,
          declared_assumptions: [],
          description:
            "Independent declared compromise scenario; not observed compromise",
          node_id: "S-1-5-21-1271839998-3495686680-2211690266-2976",
          node_kind: "User",
          profile_kind: "user_usable_identity",
          source_id:
            "source-user-f192b260682d08fbffa9d05e60c222e08c2908b2f8266eda63293f1b9abcf113",
        },
        {
          authentication_context:
            "S-1-5-21-1271839998-3495686680-2211690266-1000",
          custom_budget: null,
          declared_assumptions: [],
          description:
            "Independent declared compromise scenario; not observed compromise",
          identity_provenance_reference:
            "scenario://neo-domain/independent-compromised-network-identity",
          node_id: "S-1-5-21-1271839998-3495686680-2211690266-4118",
          node_kind: "Computer",
          profile_kind: "computer_usable_identity",
          source_id:
            "source-computer-7c1a27ef87432d62e1b85c21ece60dde67cefd4d41ea7dbfcc1e1adce8597a44",
        },
        {
          authentication_context:
            "S-1-5-21-1271839998-3495686680-2211690266-1000",
          custom_budget: null,
          declared_assumptions: [],
          description:
            "Independent declared compromise scenario; not observed compromise",
          identity_provenance_reference:
            "scenario://neo-domain/independent-compromised-network-identity",
          node_id: "S-1-5-21-1271839998-3495686680-2211690266-4096",
          node_kind: "Computer",
          profile_kind: "computer_usable_identity",
          source_id:
            "source-computer-b61990c30c6fc53198e7509eab916633549c8dcd36bbff5ea80d393e42292df6",
        },
      ],
      target_goal_ids: null,
      target_manifest: {
        default_discovery_goals: [],
        description:
          "Snapshot-derived technical candidates; impact remains Unknown",
        domain_sid: "S-1-5-21-1271839998-3495686680-2211690266",
        manifest_id: "auto-exposure-targets",
        schema_version: "target-manifest/1.2.0",
        snapshot_id:
          "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812",
        targets: [
          {
            category: "tier_0_identity",
            checkpoint_goal: null,
            description:
              "Automatically selected technical goal; business impact is unreviewed.",
            display_name: "DOMAIN ADMINS@SEAMLESS.INTERNAL",
            goal_id:
              "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
            goal_kind: "usable_identity_entitlement",
            impact_rating: "Unknown",
            provenance_locator:
              "canonical-node:S-1-5-21-1271839998-3495686680-2211690266-512",
            required_control_level: "admin_entitlement",
            required_state: {},
            target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
            target_node_kind: "Group",
            technical_consequence: "attacker_usable_group_entitlement",
          },
          {
            category: "tier_0_identity",
            checkpoint_goal: null,
            description:
              "Automatically selected technical goal; business impact is unreviewed.",
            display_name: "ENTERPRISE ADMINS@SEAMLESS.INTERNAL",
            goal_id:
              "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
            goal_kind: "usable_identity_entitlement",
            impact_rating: "Unknown",
            provenance_locator:
              "canonical-node:S-1-5-21-1271839998-3495686680-2211690266-519",
            required_control_level: "admin_entitlement",
            required_state: {},
            target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
            target_node_kind: "Group",
            technical_consequence: "attacker_usable_group_entitlement",
          },
        ],
        version: "1.0.0",
      },
    },
    runner_sha256:
      "sha256:1f8c5b4bd3dde3098378231e1c58ba25b1e2d56da75a14c15064ef6d2806cb6d",
    selection_seed: "neo-decision-v1",
    snapshot_sha256:
      "sha256:65b8c478ce48f07d3154ce6b55c21e388ab2cfe9b14d5a7dd386055b0e129cc9",
    source_pins: {
      "configs/attack_semantics.yml":
        "sha256:73d46a1d077870379e3fcc40ae5883acbb46e8160c86bb627b9dfc04a5d4d241",
      "configs/contract.yml":
        "sha256:f461e6e8d8d48b9841797da41ff9cee829b979148685f6a5185db66e23d79eea",
      "configs/targets/seamless-v2.json":
        "sha256:d58d3e692c24df603371aef78652490ada3cd48df9c65299a1364abfceffbd63",
      "docs/research/batch-query-request.schema.json":
        "sha256:428b0e31393a42c19f3fb50db7ea58f17f444d37955fed11dbb30cd7e39c7201",
      "docs/research/batch-query-result.schema.json":
        "sha256:f2d6549609953ca200eb8b88c3f3799e5d74a2f7690825533af48507580c96b2",
      "docs/research/target-manifest.schema.json":
        "sha256:a70faa520f6f094f42c17f59179d4d4bf93ff92cf1a8fc4accff840c72cf1bda",
      "requirements-tests.txt":
        "sha256:a603cf388e022db0a759e83deca59669d0ba70d8eff4eb8dd066f8c5e7d9525d",
      "requirements.txt":
        "sha256:8cc5d78b3d9261d9b800be1e36b947843b2cb5bd2b693280aade4dbfad99f89f",
      "scripts/check_contract.py":
        "sha256:10e223f8c5d22af3d6ca84851f812e0eae5dc9b8c7b68344fea916b79caf43cc",
      "scripts/research/source_goal_batch.py":
        "sha256:d064b8647818897b4898c9e89494834647a2e5c7fb8af570b28d232645265bbc",
      "src/__init__.py":
        "sha256:be6500a9bf29b09aa81cb84abe1bca4424a106eb9303a4d116d4b7ec4cf4fe44",
      "src/data/__init__.py":
        "sha256:7c416fe27da09eedffab1061c88ad906230c2f045f6943ea6fd9e56a457ae495",
      "src/data/manifest.py":
        "sha256:1833056b49caf578e2728c51a4dd4603ff999bb4abe6c58f720357f7031ef192",
      "src/engine/__init__.py":
        "sha256:78208f2c7c6f0c4f46d5f05e8f0cf356b203d414cb90209bd8c27a8a8cde87de",
      "src/engine/__main__.py":
        "sha256:7b28fccfcc6cd621f444809085ad658b176fb9425e660c49e86ae0117d860b5a",
      "src/engine/batch.py":
        "sha256:4d4a10bf5d028f7fc14b69a6ec24073450f77c7595f50a3ac84001996e5aebc0",
      "src/engine/batch_cli.py":
        "sha256:aa4b24d68acbd96d62545c11b263d8df320b7ad4755e1b11c531d9be7e6c371c",
      "src/engine/exploration.py":
        "sha256:a3561d42037eaf4b44dd7f06bd593128b32ff66940cc61ce822be3ff1dd2cb5f",
      "src/engine/graph.py":
        "sha256:9a9e00c13fa4bbeb2e3fe921249d624be0a850f99913d1b6e3697053a28c8751",
      "src/engine/program_identity.py":
        "sha256:dac98bad8af6b6c6ffee6c53b2d52540f6daea6ae45348f0e128d6f8cb232740",
      "src/engine/query.py":
        "sha256:71a7c3afd359aa6452220d9aff8c5e0410b46e7014b1e7b26efe991fb5614a6e",
      "src/engine/query_cli.py":
        "sha256:f5d577e1794c931504901ea4f535f7a95091535e655af0e0c554720e3acd941c",
      "src/engine/query_report.py":
        "sha256:00ce31a58a87bdaf948a765bc41352c272888061328ae6045a1b2976979eee26",
      "src/engine/ranking/__init__.py":
        "sha256:6995963b8df9aa2f5c44f7f7d9996039d31965301fb3a1dba96202e411f8a6d9",
      "src/engine/ranking/adapter_145.py":
        "sha256:5461ef092c04b4e8ed0338950f2a0081c671f06dc889e802e279468d535c4c54",
      "src/engine/ranking/assessment.py":
        "sha256:dd46fafa1995e907c4cd562257f0e49067b293009995f6107cc285296f8b1d1f",
      "src/engine/ranking/cli.py":
        "sha256:b6717ec5bc2d50f406736ab8bac4b66280ecbb5f55c1abdcaf3ac38474a49e4f",
      "src/engine/ranking/effort_profiles.py":
        "sha256:1021857bf06932e5c21992a75abbe1ed6a532c47b9d0bba131371128f5d1cc45",
      "src/engine/ranking/effort_registry.py":
        "sha256:03b7dfede1f1975e4f246b9efbc60f414a963814a0959bc9409966ca72b5ed23",
      "src/engine/ranking/facts.py":
        "sha256:476d434fb0adfe383d22a2e6577e37ad7cd5c0d4028e16e225e13a8a38047fd1",
      "src/engine/ranking/frontier.py":
        "sha256:06ff84f3db154dfaf04b5477443a16842232244b7a8badf1b05e5593507f2140",
      "src/engine/ranking/likelihood.py":
        "sha256:7994852a6e4aa75724cf933755ec1fdb21b6b11b62311eeaf1a87aec1b0a381e",
      "src/engine/ranking/models.py":
        "sha256:936761b7e1f246f04fad4c36e8bd62ed2bc5d2fbf02f7cfae592f6d7eb144377",
      "src/engine/ranking/orchestration.py":
        "sha256:b234540e55933d8879f302e760dfa31db5758dc018d7d6ffe223af44180d8ed3",
      "src/engine/ranking/replay.py":
        "sha256:e2671acde1ad9d97784f5ed2020446bd609d47c7a989551bcf8099648e9c7e15",
      "src/engine/ranking/reset_effort.py":
        "sha256:50a75eb6b848f74f3083e01f5fb3805995f4d56b9c14eb583890789cdec21eb1",
      "src/engine/ranking/resolution_service.py":
        "sha256:62599bdc26dd9e553bccab59ca531b419193c5f0a1b74dcc5c015905a90cc1b9",
      "src/engine/ranking/resolver.py":
        "sha256:b03a2569c28df8626af26f99dbc8f2deb18f95aa1cce37e94601227230c22240",
      "src/engine/ranking/validation.py":
        "sha256:e9b216fdde0ec0529c888c0c46df1de4b776c0f2c17e3030cff747c11b1283aa",
      "src/engine/ranking/verification.py":
        "sha256:0a9054ca62f548d806a7a45a1446cb2ec5cd4c4ada8d65088370d4c760642e61",
      "src/engine/remediation.py":
        "sha256:7f4efe55643581dbce981423cd0cd457df8570f7b871c9bad5753b1f92b3c096",
      "src/engine/remediation_runner.py":
        "sha256:2522f7915af51fc6aad5e1894dd09caaa61375a5bbfc6423c05b321b4960f858",
      "src/engine/search.py":
        "sha256:47c472297e6bd17a2fa19539cba0b257af1a21ec3822d7bce44f5d0811dfa7cc",
      "src/engine/semantics/__init__.py":
        "sha256:bbe9296904e45522947ec3294b239a2f780b24851bbfb877210273406d86ed2b",
      "src/engine/semantics/catalog.py":
        "sha256:1b15ead2aafe68d8158b16dc058f42f585ac1c7b223ffb31e3fafc45be5fbde9",
      "src/engine/semantics/credentials.py":
        "sha256:51e3ee7f004ea3cf3e6c3d14043915dd58908540ee0ce26cc6520b82792d071d",
      "src/engine/semantics/evaluator.py":
        "sha256:f660c0b60fb234d2367bc84f32a1f3560ab0c1777ab117eafd8c76a8753ea244",
      "src/engine/semantics/evidence_view.py":
        "sha256:a137bd9732dd049d011dc35dba7c27dfeebaf17476fd2c1cada0f7ce9a6fb41b",
      "src/engine/semantics/models.py":
        "sha256:5b1d8f2ae1c087b4d75d6692de0ec7d0fd33e510bca73945e0334421b78a8c05",
      "src/engine/semantics/projection_runtime.py":
        "sha256:b0f370a4dfde757b62a0d65761f492dcfb849be2567cd7a1a0dc5b35f719d91b",
      "src/engine/semantics/rbcd.py":
        "sha256:c389a9d96a88c54aa916b21f61610b77ebbcbe64540ce26e3c669605f5f01732",
      "src/engine/semantics/rbcd_types.py":
        "sha256:e818408c9404754cd7a67b6e39d302154bb71be8f01d78e10cb97f9163e08067",
      "src/engine/semantics/scenario_policy.py":
        "sha256:2b71ef4388784a319b93211e0200e910caa01a2be1dcc46a0ec265fbc63cfed2",
      "src/engine/semantics/state.py":
        "sha256:2ba649c154682920c3387cd29db9abae67e885f656c664042b009882398bb59b",
      "src/engine/semantics/transitions.py":
        "sha256:449d238519fa4dc13cad83d50c9226b1f6b18f7dd76c331b460bab047450dd10",
      "src/engine/semantics/week3.py":
        "sha256:3b42af0df172af619677749b7ea8d6f7e697a373949c5ee3883f69281883ab3b",
      "src/engine/top_k.py":
        "sha256:e2e2eb4e85ba5bc018326d7a1e98e20fe58bc847fcc9017d40018dd44f9583e0",
      "src/parser/__init__.py":
        "sha256:12dcd41fed8109dd444c0e13806a33a909a6651c172f43fdf9f39e1b4e801cc3",
      "src/parser/adapters/__init__.py":
        "sha256:f34eca65d48731f73562d43c4d57a861737804fec81da0d406217644f854f0d4",
      "src/parser/adapters/bloodhound_v3.py":
        "sha256:68b322116517215ac7f8e6838cc0e1362d5013875971e5888ecd765d78628b2a",
      "src/parser/builder.py":
        "sha256:2a62178f5c5136994cf88084c7188f16c025a257c2dd33e0de7a3624229ae5d5",
      "src/parser/cli.py":
        "sha256:61ee3729ffe44b5cbbd8b70ce5fc35efb7a14dfd48b48834ecbdb5a3a8295a12",
      "src/parser/identity_fields.py":
        "sha256:70ee89607c2506a3c8997ee4249f1e810cf99b6c5ef4b5c361ab0d0b841d0cac",
      "src/parser/inference.py":
        "sha256:0eacfcee8b70401e74a7715f0e67ecd40f59312b76d9fd3613117e313252d896",
      "src/parser/lineage.py":
        "sha256:2a9011c98a3017fb3861157b99269ffd3b879e5a4a841933b28645c1fdd1a9c2",
      "src/parser/loader.py":
        "sha256:aa69c287a5cae0ee1ae44c59e14d328522d8d598ee3652e60c949d8ee87b0fe5",
      "src/parser/normalizer.py":
        "sha256:29beeb63c2513fb0b950595195862fd5114c823eb412add72396bbe8cc9b7819",
      "src/parser/reconciliation.py":
        "sha256:53792e88875a966e1eaf0ff0aa6c6cf365d3c8093d7ab152fdc8d570b797dbba",
      "src/parser/scopes.py":
        "sha256:5a76282616933410d8da24e3a03dc311347b7c7d11136b187aba41cdf15a97af",
      "src/parser/serialization.py":
        "sha256:4cd6dd06af3b596a1b13df6c34b60bb0b40d92bd1cfbfa13ca6766b4485fe50e",
      "src/parser/snapshot_facts.py":
        "sha256:6bc8567dcb49c6f0995cc03e891f9bcdeb5883c752fab20c714f5878e2d853d2",
      "src/parser/well_known_principals.py":
        "sha256:41c038d412d3d3dc662c463dc253f6527d00baae0d8b7055808301d80627ffd8",
    },
  },
  selection:
    "Deterministic SHA order: first 3 User and 2 Computer, before inspecting results; independent declared compromise scenarios. Case panel, not a population estimate.",
  C_basis:
    "Existing neo-c-v1 expert scenario work-unit score; not elapsed time or probability. Best found, no minimum proof.",
  selected_point: {
    edge: {
      id: "sha256:431a55990c1e057f77a0c9ec37e65d7d72600c7a7913a73136a1928afa6a3f76",
      kind: "MemberOf",
      provenance: [
        {
          attribute: "Members[].MemberId",
          collector: "sharphound",
          evidence_type: "positive",
          raw_file:
            "snapshot:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812/20210920185958_groups.json",
          record_id: "SEAMLESS.INTERNAL-S-1-5-32-544",
          time_provenance_reason:
            "Explicit filename-based research collection-time convention; manifest collected_at is null and filename is not observed collection time.",
          timestamp: "2021-09-20T18:59:58Z",
          timestamp_status: "assumed",
        },
      ],
      source: "S-1-5-21-1271839998-3495686680-2211690266-1116",
      target:
        "domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-544",
      weight: 1.0,
    },
    pairs: [
      [
        "S-1-5-21-1271839998-3495686680-2211690266-1815",
        "S-1-5-21-1271839998-3495686680-2211690266-519",
      ],
      [
        "S-1-5-21-1271839998-3495686680-2211690266-2091",
        "S-1-5-21-1271839998-3495686680-2211690266-519",
      ],
      [
        "S-1-5-21-1271839998-3495686680-2211690266-2976",
        "S-1-5-21-1271839998-3495686680-2211690266-519",
      ],
      [
        "S-1-5-21-1271839998-3495686680-2211690266-4096",
        "S-1-5-21-1271839998-3495686680-2211690266-519",
      ],
      [
        "S-1-5-21-1271839998-3495686680-2211690266-4118",
        "S-1-5-21-1271839998-3495686680-2211690266-519",
      ],
    ],
    programs: 15,
  },
  intervention: {
    candidate_id:
      "sha256:4c8cefabd5d5b53f2824542185d2f323eabdab46d98397ef7e536adb90c0ac44",
    catalog_entry_id: "group-membership",
    observed_bindings: [
      {
        goal_id:
          "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
        program_id:
          "sha256:3ae8fab75f5d28e754e730ca55291190402b26380e7946754b0c5c50d45ea44d",
        source_id:
          "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
      },
      {
        goal_id:
          "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
        program_id:
          "sha256:d35b652684cbaaecce7bc13d6d5d5b5c71fd552004c1496b1ae549a51ee5d792",
        source_id:
          "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
      },
      {
        goal_id:
          "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
        program_id:
          "sha256:dae17f656a397c2c020e242f3ed5bdbaa43913eabfe2ba271005fa2555bba494",
        source_id:
          "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
      },
    ],
    prerequisites: [
      "actor_controlled",
      "actor_enabled",
      "membership_usable",
      "security_group",
      "source_authorized",
    ],
    reason: "Observed native support; exact before evidence must revalidate.",
    required_evidence: [
      "MemberOf edge and group/member record",
      "scope and token-refresh policy",
    ],
    status: "supported",
    support_scope: "native_declared_model_not_live_AD",
    technical_edits: [
      {
        catalog_entry_id: "group-membership",
        edge_id:
          "sha256:431a55990c1e057f77a0c9ec37e65d7d72600c7a7913a73136a1928afa6a3f76",
        edit_id: "inventory-6adb90c0ac44-0",
        effective_right_verified: true,
        evidence_refs: [
          "sha256:431a55990c1e057f77a0c9ec37e65d7d72600c7a7913a73136a1928afa6a3f76",
        ],
        kind: "deny_relationship",
        provenance_digest:
          "sha256:d63cba89024f6187bd67488406985c8b193c58edd97c79aecddbc66652f81297",
        rationale:
          "Observed-scope counterfactual candidate; validate operational prerequisites separately.",
        relationship: {
          kind: "MemberOf",
          source: "S-1-5-21-1271839998-3495686680-2211690266-1116",
          target:
            "domain:sid:S-1-5-21-1271839998-3495686680-2211690266:S-1-5-32-544",
        },
      },
    ],
  },
  totals: {
    baseline_programs: 30,
    new_after_programs: 15,
    pairs: 10,
    pairs_disconnected: 0,
    programs_cut: 15,
    reachable_after: 10,
    reachable_before: 10,
    sources: 5,
    unresolved_after: 0,
  },
  route_occurrences_per_pair: {
    before: 19,
    after: 19,
    cut: 5,
    new_after: 5,
  },
  verification: [
    {
      source_index: 0,
      edit_digest:
        "sha256:9f62a52a78a12ed842b92447a1b8de4c6878da365cb0799ec33cf2ad3002e723",
      package_sha256:
        "sha256:0276aea05aa7edf0eed95d463a196c9659ad49b39349f2aca5aa52df9c46882a",
      independent_verifier_passed: true,
    },
    {
      source_index: 1,
      edit_digest:
        "sha256:9f62a52a78a12ed842b92447a1b8de4c6878da365cb0799ec33cf2ad3002e723",
      package_sha256:
        "sha256:5ab16c5bd59ab31e083a6f9b1205773181e72f797cd3b8cbf3fd684b4800c371",
      independent_verifier_passed: true,
    },
    {
      source_index: 2,
      edit_digest:
        "sha256:9f62a52a78a12ed842b92447a1b8de4c6878da365cb0799ec33cf2ad3002e723",
      package_sha256:
        "sha256:68715ecdd216223c7b041398a2b5b420a6a2be7008134baba01fd7b69901ac6d",
      independent_verifier_passed: true,
    },
    {
      source_index: 3,
      edit_digest:
        "sha256:9f62a52a78a12ed842b92447a1b8de4c6878da365cb0799ec33cf2ad3002e723",
      package_sha256:
        "sha256:57a53d665d574b7d1ce42fbc947baa8a21c91d2736bfbd9933c83b4a9c3d0c28",
      independent_verifier_passed: true,
    },
    {
      source_index: 4,
      edit_digest:
        "sha256:9f62a52a78a12ed842b92447a1b8de4c6878da365cb0799ec33cf2ad3002e723",
      package_sha256:
        "sha256:03cef4262c6d9d8fdbf815f6505c44dccfeae936986dc689aab0c662155449ec",
      independent_verifier_passed: true,
    },
  ],
  cells: [
    {
      source_index: 0,
      source: "SCOTTY_HARTMAN@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-1815",
      source_kind: "User",
      source_id:
        "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
      target: "DA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
      goal_id:
        "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
      discovery: {
        status: "success",
        expansions: 26,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:96c9521cd6af6914bee2a098ac4e534f20a6ce31a31938c59a764f59a56fa1a9",
          route_id:
            "sha256:93447ba96c687507edbc1aa812a32f19e2cc6d7f85924b146dd93ac948c1a522",
          C: 2,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2014",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:f456fdd2ac324a0cb113e8585e5924d3292b99f36864710ffbdf73ba5005131a",
          route_id:
            "sha256:159525d13cdbf65285e7a69181a9f8ea5a4300007e1f674a858326bea66fb04b",
          C: 2,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2799",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:cf242ccc3084862b3d4b649ad9e8b4d0679ed4c19edaf6607a515ea89fe2430d",
          route_id:
            "sha256:f5be38c1601a68231c1d4625bf6254cb5f766eb3cdfaf59326046d995863d046",
          C: 2,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3325",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:159525d13cdbf65285e7a69181a9f8ea5a4300007e1f674a858326bea66fb04b",
            "sha256:93447ba96c687507edbc1aa812a32f19e2cc6d7f85924b146dd93ac948c1a522",
            "sha256:f5be38c1601a68231c1d4625bf6254cb5f766eb3cdfaf59326046d995863d046",
          ],
          query_digest:
            "sha256:2bdbb33c77c1866bfe01190fbfdd0d20c9bcfe659ded55f122856527df6cdd23",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:159525d13cdbf65285e7a69181a9f8ea5a4300007e1f674a858326bea66fb04b",
            "sha256:93447ba96c687507edbc1aa812a32f19e2cc6d7f85924b146dd93ac948c1a522",
            "sha256:f5be38c1601a68231c1d4625bf6254cb5f766eb3cdfaf59326046d995863d046",
          ],
          query_digest:
            "sha256:846a2befee2af09e3f1b3edd89d603ab37564de93b13d5cfe68a7dee362a6165",
        },
        effort: {
          after: 2,
          basis_refs: [
            "sha256:4fe5d8df7f22715ef048a8f561a84aed316d5fca87f0e1dac04ce1e806b4697b",
          ],
          before: 2,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [],
        cut_route_ids: [],
        new_program_ids: [],
        bypass_program_ids: [
          "sha256:96c9521cd6af6914bee2a098ac4e534f20a6ce31a31938c59a764f59a56fa1a9",
          "sha256:cf242ccc3084862b3d4b649ad9e8b4d0679ed4c19edaf6607a515ea89fe2430d",
          "sha256:f456fdd2ac324a0cb113e8585e5924d3292b99f36864710ffbdf73ba5005131a",
        ],
      },
    },
    {
      source_index: 0,
      source: "SCOTTY_HARTMAN@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-1815",
      source_kind: "User",
      source_id:
        "source-user-c8fb869ac9b89c2699b56d2815a75722d0ec1761d16d698e4e0c2e2d8c1a42c3",
      target: "EA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
      goal_id:
        "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
      discovery: {
        status: "success",
        expansions: 35,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:d35b652684cbaaecce7bc13d6d5d5b5c71fd552004c1496b1ae549a51ee5d792",
          route_id:
            "sha256:24dc0c4cd9c03f0d17e890937db885b2c1b036202beb5b1e1b2b9a11f29c5f86",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:3ae8fab75f5d28e754e730ca55291190402b26380e7946754b0c5c50d45ea44d",
          route_id:
            "sha256:24dc0c4cd9c03f0d17e890937db885b2c1b036202beb5b1e1b2b9a11f29c5f86",
          C: 6,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:dae17f656a397c2c020e242f3ed5bdbaa43913eabfe2ba271005fa2555bba494",
          route_id:
            "sha256:24dc0c4cd9c03f0d17e890937db885b2c1b036202beb5b1e1b2b9a11f29c5f86",
          C: 6,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1634",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:24dc0c4cd9c03f0d17e890937db885b2c1b036202beb5b1e1b2b9a11f29c5f86",
          ],
          query_digest:
            "sha256:9600491f906d2e7a2c6b5c8695d0e45e74d623ded1a689b2b3cd6b6ed82a15f8",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:4f3403c5867ff797b90aad87f730d589505d2a95e88d49e428504461fcc022c6",
          ],
          query_digest:
            "sha256:96c15f27e631eb74174f617706507fa6085897a0b747afb352c8f1a0b03dc765",
        },
        effort: {
          after: 5,
          basis_refs: [
            "sha256:77e83a8bc616d3c87f782a3da7ccd6e67f7db6416ba7ce30c9d5d88bab935358",
          ],
          before: 5,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [
          "sha256:3ae8fab75f5d28e754e730ca55291190402b26380e7946754b0c5c50d45ea44d",
          "sha256:d35b652684cbaaecce7bc13d6d5d5b5c71fd552004c1496b1ae549a51ee5d792",
          "sha256:dae17f656a397c2c020e242f3ed5bdbaa43913eabfe2ba271005fa2555bba494",
        ],
        cut_route_ids: [
          "sha256:24dc0c4cd9c03f0d17e890937db885b2c1b036202beb5b1e1b2b9a11f29c5f86",
        ],
        new_program_ids: [
          "sha256:08d1f9d8eebb034619d297043734f348660b3ff8089b7bdb6ee19daebb7eb387",
          "sha256:22b205983b71030a8a6e3b341e66e4319b79699716959fc5853c9d2adff19031",
          "sha256:da4909ee790a627855e56a7f9ec23379356459448576f70a41394821201e30f4",
        ],
        bypass_program_ids: [
          "sha256:08d1f9d8eebb034619d297043734f348660b3ff8089b7bdb6ee19daebb7eb387",
          "sha256:22b205983b71030a8a6e3b341e66e4319b79699716959fc5853c9d2adff19031",
          "sha256:da4909ee790a627855e56a7f9ec23379356459448576f70a41394821201e30f4",
        ],
      },
    },
    {
      source_index: 1,
      source: "BENNY_LONG@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-2091",
      source_kind: "User",
      source_id:
        "source-user-62fb91f2c503d49e7af991a5739a2fcc4d30e3a5e5ab9ca99730cd47d20753b6",
      target: "DA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
      goal_id:
        "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
      discovery: {
        status: "success",
        expansions: 20,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:3ee55a4d9a83474c0ce162b8fad78a659505b92eea5df6cf742f9f69ed98c280",
          route_id:
            "sha256:d94377583f056255d3504cb797cf37d2a012e356f41a2ea76a8903bffa4874e6",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2014",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:4100d42b0099be3abe4dfa4d8a080054f58c9fa1a2ffb4f50857998184c85080",
          route_id:
            "sha256:81a748eaf8698ebf8ccf2469e99acb41b611a98c8d8a58d1d3b6054bd9437d14",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2799",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:4c4abc264d7f4879020b61b77e190bab37b851a0f468d0b59a03e6a968bbe2b5",
          route_id:
            "sha256:11ee2e91503812ec38c54d15a1abce84b4764744e2c6406fc36d5b892ef5ffdb",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3325",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:11ee2e91503812ec38c54d15a1abce84b4764744e2c6406fc36d5b892ef5ffdb",
            "sha256:81a748eaf8698ebf8ccf2469e99acb41b611a98c8d8a58d1d3b6054bd9437d14",
            "sha256:d94377583f056255d3504cb797cf37d2a012e356f41a2ea76a8903bffa4874e6",
          ],
          query_digest:
            "sha256:01de05bd32af5086287559db9a05d3b5c30c486190e7c5dd8c4fea5efed40e89",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:11ee2e91503812ec38c54d15a1abce84b4764744e2c6406fc36d5b892ef5ffdb",
            "sha256:81a748eaf8698ebf8ccf2469e99acb41b611a98c8d8a58d1d3b6054bd9437d14",
            "sha256:d94377583f056255d3504cb797cf37d2a012e356f41a2ea76a8903bffa4874e6",
          ],
          query_digest:
            "sha256:1072e5efeda5be19863e3d356128ccff5b9feb6b8a644d1bb1f03ef8819f75f3",
        },
        effort: {
          after: 1,
          basis_refs: [
            "sha256:1be3fe6a2100bc145b0e3d5dfc0a60e95b9d112d80ff21c7afb6a16e44891a43",
          ],
          before: 1,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [],
        cut_route_ids: [],
        new_program_ids: [],
        bypass_program_ids: [
          "sha256:3ee55a4d9a83474c0ce162b8fad78a659505b92eea5df6cf742f9f69ed98c280",
          "sha256:4100d42b0099be3abe4dfa4d8a080054f58c9fa1a2ffb4f50857998184c85080",
          "sha256:4c4abc264d7f4879020b61b77e190bab37b851a0f468d0b59a03e6a968bbe2b5",
        ],
      },
    },
    {
      source_index: 1,
      source: "BENNY_LONG@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-2091",
      source_kind: "User",
      source_id:
        "source-user-62fb91f2c503d49e7af991a5739a2fcc4d30e3a5e5ab9ca99730cd47d20753b6",
      target: "EA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
      goal_id:
        "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
      discovery: {
        status: "success",
        expansions: 28,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:1671b53c84674b71bcc13e2d4af86053f0799a6aa610bec6661edac484114e45",
          route_id:
            "sha256:221b82316f9f69abf6a14e00db90055f2acf0342e1063e091e060dc8e6ea1440",
          C: 4,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:dd1c3af26232d21b76227a21478817dca35bfa894c71e81541e7930308ba6cb4",
          route_id:
            "sha256:221b82316f9f69abf6a14e00db90055f2acf0342e1063e091e060dc8e6ea1440",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:247fe7bc1adb656714fab8756240f815afa5461fd95feb17860070b885de8596",
          route_id:
            "sha256:221b82316f9f69abf6a14e00db90055f2acf0342e1063e091e060dc8e6ea1440",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:221b82316f9f69abf6a14e00db90055f2acf0342e1063e091e060dc8e6ea1440",
          ],
          query_digest:
            "sha256:7cbad15121b516e2a8377c525f69c1182d393c9a83cec4f578dbb15239966a14",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:4595629883d63fdfc05e376f31c344dfbc7fb252c8a28779176f264c11d8810e",
          ],
          query_digest:
            "sha256:82612c8f46a6321772becfbcbc2aacfb8b394384745ff76d385b30e852e65ead",
        },
        effort: {
          after: 4,
          basis_refs: [
            "sha256:7d5fd729bff9cc4f571632575d49562e6981a0c1961c7f79a5189aa58bdc5bb9",
          ],
          before: 4,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [
          "sha256:1671b53c84674b71bcc13e2d4af86053f0799a6aa610bec6661edac484114e45",
          "sha256:247fe7bc1adb656714fab8756240f815afa5461fd95feb17860070b885de8596",
          "sha256:dd1c3af26232d21b76227a21478817dca35bfa894c71e81541e7930308ba6cb4",
        ],
        cut_route_ids: [
          "sha256:221b82316f9f69abf6a14e00db90055f2acf0342e1063e091e060dc8e6ea1440",
        ],
        new_program_ids: [
          "sha256:05496f06309402ab7c06e1e8a146d08da078c749051696d635b8ee9777746adf",
          "sha256:1109bbaa3efd54e62ac5158abde306e48b0bfa30a1acc9f23a97cc0eb6bd5733",
          "sha256:3029e664603db47fc92a3f2f03855179f65c7f17cfd56f21e30c36db91317de9",
        ],
        bypass_program_ids: [
          "sha256:05496f06309402ab7c06e1e8a146d08da078c749051696d635b8ee9777746adf",
          "sha256:1109bbaa3efd54e62ac5158abde306e48b0bfa30a1acc9f23a97cc0eb6bd5733",
          "sha256:3029e664603db47fc92a3f2f03855179f65c7f17cfd56f21e30c36db91317de9",
        ],
      },
    },
    {
      source_index: 2,
      source: "EVAN_LOTT@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-2976",
      source_kind: "User",
      source_id:
        "source-user-f192b260682d08fbffa9d05e60c222e08c2908b2f8266eda63293f1b9abcf113",
      target: "DA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
      goal_id:
        "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
      discovery: {
        status: "success",
        expansions: 20,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:e70e5ce778be252da3dc27f8e13c6fead0207196bacc2c92235a3e5784b0d322",
          route_id:
            "sha256:5510d73c3cfeb84955ae658c17f33646339416e5b25296b4e1c123d9a9bc3696",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2014",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:d10ad9229a7544a79406055ab243dd65c7eb4bd8d1d492bb5a3fa76a572a75de",
          route_id:
            "sha256:ad9e05227aa5716685a90d31560609c7d8eb8c98cc9876c4cbfcd7afbb153e8f",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2799",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:97bf9e6f0b159c49be2e226a0ae9335c35a3243e7a57617c3c1a4911dba8cc96",
          route_id:
            "sha256:050b7bc732ac4872d5bf2882925d7c1fd5c26cf6688bff409044e304a66117f9",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3325",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:050b7bc732ac4872d5bf2882925d7c1fd5c26cf6688bff409044e304a66117f9",
            "sha256:5510d73c3cfeb84955ae658c17f33646339416e5b25296b4e1c123d9a9bc3696",
            "sha256:ad9e05227aa5716685a90d31560609c7d8eb8c98cc9876c4cbfcd7afbb153e8f",
          ],
          query_digest:
            "sha256:ca24ed6f5964968960c52f11adf52a67fffa9ccfbe8172931c2d94b48335ae1f",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:050b7bc732ac4872d5bf2882925d7c1fd5c26cf6688bff409044e304a66117f9",
            "sha256:5510d73c3cfeb84955ae658c17f33646339416e5b25296b4e1c123d9a9bc3696",
            "sha256:ad9e05227aa5716685a90d31560609c7d8eb8c98cc9876c4cbfcd7afbb153e8f",
          ],
          query_digest:
            "sha256:74a255c1a0f07e968262a61a34c10a49127f634ca91cbb558ecbee8388de20a2",
        },
        effort: {
          after: 1,
          basis_refs: [
            "sha256:0b9c391c4c63602dc549a608d43a3447b0d4c29ce4a8043589d383d311f383cb",
          ],
          before: 1,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [],
        cut_route_ids: [],
        new_program_ids: [],
        bypass_program_ids: [
          "sha256:97bf9e6f0b159c49be2e226a0ae9335c35a3243e7a57617c3c1a4911dba8cc96",
          "sha256:d10ad9229a7544a79406055ab243dd65c7eb4bd8d1d492bb5a3fa76a572a75de",
          "sha256:e70e5ce778be252da3dc27f8e13c6fead0207196bacc2c92235a3e5784b0d322",
        ],
      },
    },
    {
      source_index: 2,
      source: "EVAN_LOTT@SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-2976",
      source_kind: "User",
      source_id:
        "source-user-f192b260682d08fbffa9d05e60c222e08c2908b2f8266eda63293f1b9abcf113",
      target: "EA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
      goal_id:
        "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
      discovery: {
        status: "success",
        expansions: 28,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:fe3e3df81e50751c1649f709d7c16a6eecdb52c7f90ef642904f74920e3af0e1",
          route_id:
            "sha256:9c5d8a5080212c9e6cdf397c0f72052ac42e3f5e9e11b2650f80cbe7c81f7d66",
          C: 4,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:df05370b12e753e6f78f4471b02c7d46ddf159cb536d2bfd7e3bd1a6e7da4731",
          route_id:
            "sha256:9c5d8a5080212c9e6cdf397c0f72052ac42e3f5e9e11b2650f80cbe7c81f7d66",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:e8c8f172fe3988c456ac29534e8b300e6651b01c6271259dd47ad9f6be9eadb1",
          route_id:
            "sha256:9c5d8a5080212c9e6cdf397c0f72052ac42e3f5e9e11b2650f80cbe7c81f7d66",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:9c5d8a5080212c9e6cdf397c0f72052ac42e3f5e9e11b2650f80cbe7c81f7d66",
          ],
          query_digest:
            "sha256:8954b417d46cd0f06aaf73b38a2e73192a5a288dc769423714a5b4dddde5520e",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:4bfd189ebf740128e7f29a6bfa1eb176db46be459213856c7fa140118f430eef",
          ],
          query_digest:
            "sha256:931724351df68a668fd9225c08380c53164320b8e84c364c03b0dcc285b30bd3",
        },
        effort: {
          after: 4,
          basis_refs: [
            "sha256:e6d753d15a8fcd5ef675e1fc23380439515d3b0161b064d4dc23eef90981209e",
          ],
          before: 4,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [
          "sha256:df05370b12e753e6f78f4471b02c7d46ddf159cb536d2bfd7e3bd1a6e7da4731",
          "sha256:e8c8f172fe3988c456ac29534e8b300e6651b01c6271259dd47ad9f6be9eadb1",
          "sha256:fe3e3df81e50751c1649f709d7c16a6eecdb52c7f90ef642904f74920e3af0e1",
        ],
        cut_route_ids: [
          "sha256:9c5d8a5080212c9e6cdf397c0f72052ac42e3f5e9e11b2650f80cbe7c81f7d66",
        ],
        new_program_ids: [
          "sha256:08813320c2bc7d93b31ddbe3bb811a4ec274a79d2567fd8c757cf9eed96d6ef3",
          "sha256:c860f76bde4f350b45e7a42863787c843bd69ddecee77addaf12cc001a851fae",
          "sha256:f079481f9d5f2ee34515f6fd561da7ba41c82224ff7b0899ab3fe42fc101716c",
        ],
        bypass_program_ids: [
          "sha256:08813320c2bc7d93b31ddbe3bb811a4ec274a79d2567fd8c757cf9eed96d6ef3",
          "sha256:c860f76bde4f350b45e7a42863787c843bd69ddecee77addaf12cc001a851fae",
          "sha256:f079481f9d5f2ee34515f6fd561da7ba41c82224ff7b0899ab3fe42fc101716c",
        ],
      },
    },
    {
      source_index: 3,
      source: "OGCWAPPS1000000.SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-4118",
      source_kind: "Computer",
      source_id:
        "source-computer-7c1a27ef87432d62e1b85c21ece60dde67cefd4d41ea7dbfcc1e1adce8597a44",
      target: "DA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
      goal_id:
        "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
      discovery: {
        status: "success",
        expansions: 20,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:661c9a45d66b4b67502c76b4ab618acd4245ded5eba3e9438bc84ef8284da65f",
          route_id:
            "sha256:fb671c6f5666daf69dd6370102ea6e23f2e57c385c5b2252441d50aff9421863",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2014",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:7395cc14dde67ccc7d278e86e3e6dcac16c7842fe7a0d0750825dcfc04a48a87",
          route_id:
            "sha256:1a3e36b4e12b9661076aac61809421062f2035dbc792f4338740e481b474b435",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2799",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:efec3fd61b5dccd9dd7ab896238296c808e5312620fd5a699d88bf6628cf0588",
          route_id:
            "sha256:4a58ba68393cd5ef2d55b2c65694787348c0d1c97e0785894760556bd7dd9de6",
          C: 1,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3325",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:1a3e36b4e12b9661076aac61809421062f2035dbc792f4338740e481b474b435",
            "sha256:4a58ba68393cd5ef2d55b2c65694787348c0d1c97e0785894760556bd7dd9de6",
            "sha256:fb671c6f5666daf69dd6370102ea6e23f2e57c385c5b2252441d50aff9421863",
          ],
          query_digest:
            "sha256:1c78dee2d84fdd1198d485e51727557d31ce75889dbd22f6fb5efe3496681221",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 3,
          route_ids: [
            "sha256:1a3e36b4e12b9661076aac61809421062f2035dbc792f4338740e481b474b435",
            "sha256:4a58ba68393cd5ef2d55b2c65694787348c0d1c97e0785894760556bd7dd9de6",
            "sha256:fb671c6f5666daf69dd6370102ea6e23f2e57c385c5b2252441d50aff9421863",
          ],
          query_digest:
            "sha256:8378e953f133c347d158582c141dcdc1fc4317a6d6f05ad96b5a3241997bf1dc",
        },
        effort: {
          after: 1,
          basis_refs: [
            "sha256:3a33e36f9a92e5109aeee1e6f3a2d8d2ddfa1549db6dff93c56153dacfea6cbe",
          ],
          before: 1,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [],
        cut_route_ids: [],
        new_program_ids: [],
        bypass_program_ids: [
          "sha256:661c9a45d66b4b67502c76b4ab618acd4245ded5eba3e9438bc84ef8284da65f",
          "sha256:7395cc14dde67ccc7d278e86e3e6dcac16c7842fe7a0d0750825dcfc04a48a87",
          "sha256:efec3fd61b5dccd9dd7ab896238296c808e5312620fd5a699d88bf6628cf0588",
        ],
      },
    },
    {
      source_index: 3,
      source: "OGCWAPPS1000000.SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-4118",
      source_kind: "Computer",
      source_id:
        "source-computer-7c1a27ef87432d62e1b85c21ece60dde67cefd4d41ea7dbfcc1e1adce8597a44",
      target: "EA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
      goal_id:
        "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
      discovery: {
        status: "success",
        expansions: 27,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:dbaac3dbd7e147be071dd5a8d1b611a84a38fef3879f107ea4ee2abc51aa9ea5",
          route_id:
            "sha256:1db213bf8d7d4df481a3d06619fd573c244ef510d257f1d85e076b712c7110ae",
          C: 4,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:3b8d5fcc6cf472fe6e5d108e8187a84908971a3aae891a248a4a0f7d63f1b2aa",
          route_id:
            "sha256:1db213bf8d7d4df481a3d06619fd573c244ef510d257f1d85e076b712c7110ae",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:16e8ffca0301e724c0a9326a42dc0576ad02bc73c6c0ca05d6cbd0b5ace3e14a",
          route_id:
            "sha256:1db213bf8d7d4df481a3d06619fd573c244ef510d257f1d85e076b712c7110ae",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:1db213bf8d7d4df481a3d06619fd573c244ef510d257f1d85e076b712c7110ae",
          ],
          query_digest:
            "sha256:6840bb2743eb0d78fb5e5aadf6b094d7109c6393399f517815fc1fe5d33863ff",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:67d606b92482270239378736d981d127537e0ae55d1e12c49a5c685b22202bb8",
          ],
          query_digest:
            "sha256:18109f5c9e454a22e59cde7658664360939c0a2d98fb433491c72cae5ca8f2ea",
        },
        effort: {
          after: 4,
          basis_refs: [
            "sha256:eb346bfc47b169123c395a3a231a7abf0c100a51ff3f995a4cdaa1ee70a210e1",
          ],
          before: 4,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [
          "sha256:16e8ffca0301e724c0a9326a42dc0576ad02bc73c6c0ca05d6cbd0b5ace3e14a",
          "sha256:3b8d5fcc6cf472fe6e5d108e8187a84908971a3aae891a248a4a0f7d63f1b2aa",
          "sha256:dbaac3dbd7e147be071dd5a8d1b611a84a38fef3879f107ea4ee2abc51aa9ea5",
        ],
        cut_route_ids: [
          "sha256:1db213bf8d7d4df481a3d06619fd573c244ef510d257f1d85e076b712c7110ae",
        ],
        new_program_ids: [
          "sha256:27e3da35f0a43a211c177b994732f3e844578d2841e9274f4cb62e321ccaab22",
          "sha256:57c4de67199d483e0f8a13b1e720ee1a843f3faf925b3797b52fface956b8386",
          "sha256:ffeec3c48ecf4cdf5becf9bc9a2c2b524a0a779021e91fcfa29dab26f8b0aa81",
        ],
        bypass_program_ids: [
          "sha256:27e3da35f0a43a211c177b994732f3e844578d2841e9274f4cb62e321ccaab22",
          "sha256:57c4de67199d483e0f8a13b1e720ee1a843f3faf925b3797b52fface956b8386",
          "sha256:ffeec3c48ecf4cdf5becf9bc9a2c2b524a0a779021e91fcfa29dab26f8b0aa81",
        ],
      },
    },
    {
      source_index: 4,
      source: "ITSWWEBS1000000.SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-4096",
      source_kind: "Computer",
      source_id:
        "source-computer-b61990c30c6fc53198e7509eab916633549c8dcd36bbff5ea80d393e42292df6",
      target: "DA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-512",
      goal_id:
        "auto-0-7e419334c57e39a1ce46c2f1b59517d17e0b428c174e5776a9f6c236c6f78800",
      discovery: {
        status: "success",
        expansions: 28,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:5b8b427c3ed01ec91d8effc70e2e3e89cd3ecfaf7e6596eba4c3852c27644f41",
          route_id:
            "sha256:a53cf2731cdfb7ed11594f4842a7654083b0f66789c9df25112e33d676956002",
          C: 2,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3398",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1310",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:ec6b88dd2220afd32c7f584718e3250587da2a3c6c0653b4d4abd5ef724b7a2d",
          route_id:
            "sha256:77462893cb7cb675e2f85d90ac11036f0cd02fef2a18be92e848394ab84adad4",
          C: 3,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3398",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3398",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1310",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:8b316bbe5ecbc3a0dcd5abc144ffd7939a6d06e678f4d3d8bacccba699a3f650",
          route_id:
            "sha256:77462893cb7cb675e2f85d90ac11036f0cd02fef2a18be92e848394ab84adad4",
          C: 3,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3398",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-3398",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1310",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 2,
          route_ids: [
            "sha256:77462893cb7cb675e2f85d90ac11036f0cd02fef2a18be92e848394ab84adad4",
            "sha256:a53cf2731cdfb7ed11594f4842a7654083b0f66789c9df25112e33d676956002",
          ],
          query_digest:
            "sha256:16c96dea4c0617c5a9693b81b22bd1c4971e85be3f4028b30dcd94fed81ce1c8",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 2,
          route_ids: [
            "sha256:77462893cb7cb675e2f85d90ac11036f0cd02fef2a18be92e848394ab84adad4",
            "sha256:a53cf2731cdfb7ed11594f4842a7654083b0f66789c9df25112e33d676956002",
          ],
          query_digest:
            "sha256:62bf56f181d03c08758fd11aebd5fa0239751e00d304c0a2455d8595d346d58a",
        },
        effort: {
          after: 2,
          basis_refs: [
            "sha256:c4fc321aa438229b6be15170e4e678e9a19b181b4f912f3117055d5a61930331",
          ],
          before: 2,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [],
        cut_route_ids: [],
        new_program_ids: [],
        bypass_program_ids: [
          "sha256:5b8b427c3ed01ec91d8effc70e2e3e89cd3ecfaf7e6596eba4c3852c27644f41",
          "sha256:8b316bbe5ecbc3a0dcd5abc144ffd7939a6d06e678f4d3d8bacccba699a3f650",
          "sha256:ec6b88dd2220afd32c7f584718e3250587da2a3c6c0653b4d4abd5ef724b7a2d",
        ],
      },
    },
    {
      source_index: 4,
      source: "ITSWWEBS1000000.SEAMLESS.INTERNAL",
      source_node_id: "S-1-5-21-1271839998-3495686680-2211690266-4096",
      source_kind: "Computer",
      source_id:
        "source-computer-b61990c30c6fc53198e7509eab916633549c8dcd36bbff5ea80d393e42292df6",
      target: "EA",
      target_node_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
      goal_id:
        "auto-0-a74f3bbfee0f031621a2fff866f17fb32658fe327436faf1ec613208243cea7e",
      discovery: {
        status: "success",
        expansions: 19,
        truncated: true,
        minimum_proven: false,
        unknown_attempts: 0,
      },
      programs: [
        {
          program_id:
            "sha256:d1a94e0543516107e025f057b19f1bf1bec9d851bb64cca7883b8f44b40d1977",
          route_id:
            "sha256:7b35d65110d2eedcf5de44d5ff06497e09af156a2a5b69c84b62ea27cb81384c",
          C: 5,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2468",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:93f23d18e00cdd40752a6bf59e9cb5a8a85712e11030f89c80d29af9db0ce09f",
          route_id:
            "sha256:7b35d65110d2eedcf5de44d5ff06497e09af156a2a5b69c84b62ea27cb81384c",
          C: 6,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2468",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
        {
          program_id:
            "sha256:809b08a5f85058ac234f73818034829960cd826fde06eb8efd04fcd423076177",
          route_id:
            "sha256:7b35d65110d2eedcf5de44d5ff06497e09af156a2a5b69c84b62ea27cb81384c",
          C: 6,
          work_units: [
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "acquire_reset_identity",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1000",
              computed_cost: 0,
              method: "AuthenticationControl",
              t1: 1,
              t2: 1,
            },
            {
              technique: "genericall_add_member",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "genericall_grant_write_dacl",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "grant_new_object_right",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-519",
              computed_cost: 2,
              method: "WriteDacl",
              t1: 2,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-1116",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
            {
              technique: "scenario_reset_password",
              target_id: "S-1-5-21-1271839998-3495686680-2211690266-2468",
              computed_cost: 1,
              method: "GenericAll",
              t1: 1,
              t2: 2,
            },
          ],
        },
      ],
      intervention_result: {
        before: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:7b35d65110d2eedcf5de44d5ff06497e09af156a2a5b69c84b62ea27cb81384c",
          ],
          query_digest:
            "sha256:b9fa47f61071d5c72b359b38453c7fc82ed4dd65a3f20f0f136aa750fb31e635",
        },
        after: {
          reachability: "reachable",
          complete: false,
          program_count: 3,
          route_count: 1,
          route_ids: [
            "sha256:14a7b1abf7927dbf2eee677887cc4cbb4d826bc8c7f15c7f70cc4293dbb2090a",
          ],
          query_digest:
            "sha256:ced991da8efd046f6298bfe042083aa892d479f9c22afb8911207a4c81060700",
        },
        effort: {
          after: 5,
          basis_refs: [
            "sha256:6845dec4e0331a820112792e99b5ed955c654d275aa5669c6301fb429a769e07",
          ],
          before: 5,
          delta: null,
          proof_refs: [],
          status: "incumbent",
          unit: "native_engine_effort_score",
        },
        disconnected: false,
        cut_program_ids: [
          "sha256:809b08a5f85058ac234f73818034829960cd826fde06eb8efd04fcd423076177",
          "sha256:93f23d18e00cdd40752a6bf59e9cb5a8a85712e11030f89c80d29af9db0ce09f",
          "sha256:d1a94e0543516107e025f057b19f1bf1bec9d851bb64cca7883b8f44b40d1977",
        ],
        cut_route_ids: [
          "sha256:7b35d65110d2eedcf5de44d5ff06497e09af156a2a5b69c84b62ea27cb81384c",
        ],
        new_program_ids: [
          "sha256:33c9055c152bfa50fbc729e6744f71ed243c16c6a049961d6baafe75b5250884",
          "sha256:62a79a4470143f0144f76a630b16ecd8ef55e434d13af8be5e63479d1dd12d0e",
          "sha256:689696772262855df6f0e6158bda8d1156c50ea7eb15308a0d524f87000a5fea",
        ],
        bypass_program_ids: [
          "sha256:33c9055c152bfa50fbc729e6744f71ed243c16c6a049961d6baafe75b5250884",
          "sha256:62a79a4470143f0144f76a630b16ecd8ef55e434d13af8be5e63479d1dd12d0e",
          "sha256:689696772262855df6f0e6158bda8d1156c50ea7eb15308a0d524f87000a5fea",
        ],
      },
    },
  ],
  bypass_example: {
    source_index: 0,
    target: "EA",
    program_id:
      "sha256:08d1f9d8eebb034619d297043734f348660b3ff8089b7bdb6ee19daebb7eb387",
    route_id:
      "sha256:4f3403c5867ff797b90aad87f730d589505d2a95e88d49e428504461fcc022c6",
    steps: [
      {
        technique_id: "propagate_group_entitlement",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-1815",
        source: "S-1-5-21-1271839998-3495686680-2211690266-1815",
        target: "S-1-5-21-1271839998-3495686680-2211690266-3807",
      },
      {
        technique_id: "scenario_reset_password",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-1815",
        source: "S-1-5-21-1271839998-3495686680-2211690266-3807",
        target: "S-1-5-21-1271839998-3495686680-2211690266-1634",
      },
      {
        technique_id: "acquire_reset_identity",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-1634",
        source: "S-1-5-21-1271839998-3495686680-2211690266-1634",
        target: "S-1-5-21-1271839998-3495686680-2211690266-1000",
      },
      {
        technique_id: "propagate_group_entitlement",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-1634",
        source: "S-1-5-21-1271839998-3495686680-2211690266-1634",
        target: "S-1-5-21-1271839998-3495686680-2211690266-3943",
      },
      {
        technique_id: "scenario_reset_password",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-1634",
        source: "S-1-5-21-1271839998-3495686680-2211690266-3943",
        target: "S-1-5-21-1271839998-3495686680-2211690266-2014",
      },
      {
        technique_id: "acquire_reset_identity",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        target: "S-1-5-21-1271839998-3495686680-2211690266-1000",
      },
      {
        technique_id: "propagate_group_entitlement",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        target: "S-1-5-21-1271839998-3495686680-2211690266-512",
      },
      {
        technique_id: "grant_new_object_right",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-512",
        target: "S-1-5-21-1271839998-3495686680-2211690266-519",
      },
      {
        technique_id: "genericall_grant_write_dacl",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        target: "S-1-5-21-1271839998-3495686680-2211690266-519",
      },
      {
        technique_id: "genericall_add_member",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        target: "S-1-5-21-1271839998-3495686680-2211690266-519",
      },
      {
        technique_id: "propagate_group_entitlement",
        actor: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        source: "S-1-5-21-1271839998-3495686680-2211690266-2014",
        target: "S-1-5-21-1271839998-3495686680-2211690266-519",
      },
    ],
  },
};
