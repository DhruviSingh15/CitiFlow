const { expect } = require("chai");
const { ethers }  = require("hardhat");

describe("CrossBorderSettlement", function () {
  let contract, owner, other;

  beforeEach(async () => {
    [owner, other] = await ethers.getSigners();
    const Factory  = await ethers.getContractFactory("CrossBorderSettlement");
    contract       = await Factory.deploy();
    await contract.waitForDeployment();
  });

  it("deploys with owner set", async () => {
    expect(await contract.owner()).to.equal(owner.address);
    expect(await contract.recordCount()).to.equal(0n);
  });

  it("creates a settlement record", async () => {
    const tx = await contract.createSettlement(
      "TXN001", "CORP_1", "VENDOR_1",
      100000n, "INR", "RAIL_B", "hash123"
    );
    await tx.wait();

    expect(await contract.recordCount()).to.equal(1n);
    const record = await contract.getSettlement(1n);
    expect(record.transactionRef).to.equal("TXN001");
    expect(record.amount).to.equal(100000n);
    expect(record.status).to.equal(0n); // CREATED
  });

  it("rejects duplicate txRef", async () => {
    await contract.createSettlement("TXN002","S","R",1n,"INR","RAIL_A","h");
    await expect(
      contract.createSettlement("TXN002","S","R",1n,"INR","RAIL_A","h")
    ).to.be.revertedWith("txRef already exists");
  });

  it("updates status through lifecycle", async () => {
    await contract.createSettlement("TXN003","S","R",500n,"SGD","RAIL_C","h");
    await contract.updateStatus(1n, 4n); // SETTLED
    const record = await contract.getSettlement(1n);
    expect(record.status).to.equal(4n);
  });

  it("looks up record by txRef", async () => {
    await contract.createSettlement("TXN004","S","R",200n,"AED","RAIL_B","h");
    const record = await contract.getByRef("TXN004");
    expect(record.selectedRail).to.equal("RAIL_B");
  });

  it("rejects non-owner calls", async () => {
    await expect(
      contract.connect(other).createSettlement("TXN005","S","R",1n,"INR","RAIL_A","h")
    ).to.be.revertedWith("not authorized");
  });

  it("emits SettlementCreated event", async () => {
    await expect(
      contract.createSettlement("TXN006","S","R",999n,"USD","RAIL_C","h")
    ).to.emit(contract, "SettlementCreated")
      .withArgs(1n, "TXN006", owner.address, 999n, "USD", "RAIL_C");
  });
});
