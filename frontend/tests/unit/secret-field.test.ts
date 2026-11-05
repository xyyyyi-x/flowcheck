import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import {
  buildHeader,
  buildVariable,
  type EditableVariable,
} from "../../src/api/secretPayload";
import SecretField from "../../src/components/SecretField.vue";

describe("SecretField", () => {
  it("defaults to keep mode and hides the value input", () => {
    const wrapper = mount(SecretField, {
      props: { hasValue: true, mode: "keep", modelValue: "" },
    });
    const select = wrapper.get("select");
    expect((select.element as HTMLSelectElement).value).toBe("keep");
    expect(wrapper.find("input").exists()).toBe(false);
    expect(wrapper.text()).toContain("将保留原值");
  });

  it("shows an input when replacing or when no value exists", async () => {
    const wrapper = mount(SecretField, {
      props: { hasValue: true, mode: "keep", modelValue: "" },
    });
    await wrapper.get("select").setValue("replace");
    expect(wrapper.emitted("update:mode")?.[0]).toEqual(["replace"]);
    await wrapper.setProps({ mode: "replace" });
    expect(wrapper.find('input[type="password"]').exists()).toBe(true);

    const fresh = mount(SecretField, {
      props: { hasValue: false, mode: "replace", modelValue: "" },
    });
    expect(fresh.find('input[type="password"]').exists()).toBe(true);
    expect(fresh.text()).toContain("必须填写非空值");
  });

  it("emits remove mode", async () => {
    const wrapper = mount(SecretField, {
      props: { hasValue: true, mode: "keep", modelValue: "" },
    });
    await wrapper.get("select").setValue("remove");
    expect(wrapper.emitted("update:mode")?.[0]).toEqual(["remove"]);
    await wrapper.setProps({ mode: "remove" });
    expect(wrapper.text()).toContain("保存后移除");
  });
});

describe("secret payload protocol", () => {
  const base: EditableVariable = {
    name: "token",
    value: "",
    is_secret: true,
    has_value: true,
    mode: "keep",
  };

  it("keep sends null so the backend retains the old secret", () => {
    expect(buildVariable(base)).toEqual({ name: "token", value: null, is_secret: true });
  });

  it("replace sends the new value and requires non-empty", () => {
    expect(buildVariable({ ...base, mode: "replace", value: "new" })).toEqual({
      name: "token",
      value: "new",
      is_secret: true,
    });
    expect(() => buildVariable({ ...base, mode: "replace", value: "" })).toThrow();
  });

  it("remove omits the item from the payload", () => {
    expect(buildVariable({ ...base, mode: "remove" })).toBeNull();
    expect(
      buildHeader({
        name: "X-Key",
        value: "",
        is_secret: true,
        has_value: true,
        mode: "remove",
      }),
    ).toBeNull();
  });

  it("parses non-secret scalars", () => {
    expect(
      buildVariable({
        name: "count",
        value: "3",
        is_secret: false,
        has_value: false,
        mode: "replace",
      }),
    ).toEqual({ name: "count", value: 3, is_secret: false });
    expect(
      buildVariable({
        name: "flag",
        value: "true",
        is_secret: false,
        has_value: false,
        mode: "replace",
      }),
    ).toEqual({ name: "flag", value: true, is_secret: false });
  });
});
